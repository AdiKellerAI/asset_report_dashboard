"""Auto-fetched current property value estimate (RentCast's AVM API, by
address) - Adi's request, 2026-08-27: show today's value next to the
purchase price on /manage.

Cached in the DB (Property.current_value / current_value_updated_at), not
in memory like app/fx.py's exchange rate - this app runs on Vercel's
serverless platform, where an in-memory cache resets on every cold start,
which would blow through RentCast's free-tier 50-requests/month cap fast
for no reason. Refreshed lazily on a /manage visit once the stored value
is stale enough - 48h (not 24h, and tightened again from an initial 36h
attempt), to hold 2 properties' refreshes to ~30 requests/month rather
than ~40-60 (Adi's request, 2026-08-28 - deliberate headroom under
RentCast's 50 cap, not just "whatever survives it"). There's no
background scheduler in this app, so "about once a day" is approximated
as "whenever someone next opens Manage after 48h have passed" - the same
lazy-refresh-on-visit shape as get_usd_to_ils_rate(), just DB-backed
instead of in-memory since the interval is much longer than one process's
lifetime on serverless.

That 36h interval is only a soft heuristic, tuned to average out under the
cap - it doesn't actually enforce anything on its own (e.g. if more
properties get added later, or the interval math is ever wrong, it
wouldn't stop calls once the free tier's limit is hit). RentcastUsage
(app/models.py) is the real, hard guardrail (Adi's request, 2026-08-28):
one row per calendar month, incremented on every attempted call regardless
of outcome, checked before every call - refresh_current_value() refuses to
call RentCast at all once the current month's count reaches the cap, no
matter how stale a property's value is.
"""

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from app.config import Config
from app.models import PropertyValueHistory, RentcastUsage

RENTCAST_VALUE_URL = "https://api.rentcast.io/v1/avm/value"
RENTCAST_RECORDS_URL = "https://api.rentcast.io/v1/properties"
REFRESH_INTERVAL = timedelta(hours=48)
# Sale history and tax assessments (see refresh_value_history() below)
# barely ever change - a county reassesses property values at most once a
# year, a sale is a rare event - so this is refreshed far less often than
# the AVM value above, deliberately keeping its share of the monthly quota
# small (Adi's request, 2026-08-28: ~30 requests/month total across
# everything this app calls RentCast for).
HISTORY_REFRESH_INTERVAL = timedelta(days=30)
MONTHLY_REQUEST_CAP = 50  # RentCast's free-tier limit


def _current_month_key():
    return date.today().strftime("%Y-%m")


def requests_used_this_month(session):
    """Public - the Manage page displays this alongside the cap so Adi can
    see how much headroom is left without needing DB access."""
    usage = session.query(RentcastUsage).filter_by(year_month=_current_month_key()).first()
    return usage.request_count if usage else 0


def _record_request(session):
    key = _current_month_key()
    usage = session.query(RentcastUsage).filter_by(year_month=key).first()
    if usage is None:
        usage = RentcastUsage(year_month=key, request_count=0)
        session.add(usage)
    usage.request_count += 1
    session.commit()


def refresh_current_value(prop, session):
    """Updates `prop.current_value` / `current_value_updated_at` in place
    (and commits) if stale, under the monthly cap, and an API key +
    address are available - silently leaves the existing (possibly still
    None) value alone on any failure, so a RentCast outage, an exhausted
    quota, or a missing key never breaks the Manage page."""
    if not Config.RENTCAST_API_KEY or not prop.address:
        return
    if prop.current_value_updated_at and datetime.utcnow() - prop.current_value_updated_at < REFRESH_INTERVAL:
        return
    if requests_used_this_month(session) >= MONTHLY_REQUEST_CAP:
        return

    # Counted as soon as the call is attempted, not only on success - a
    # request that reaches RentCast's server but comes back as an error
    # (rate limit, bad address, etc.) may well still count against their
    # quota, so this stays conservative about ours too. A pure network
    # failure that never left this machine "wastes" one counted attempt
    # it didn't need to, which is an acceptable trade for never
    # overshooting the real cap.
    _record_request(session)

    try:
        url = f"{RENTCAST_VALUE_URL}?{urllib.parse.urlencode({'address': prop.address})}"
        request = urllib.request.Request(url, headers={"X-Api-Key": Config.RENTCAST_API_KEY})
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read())
        price = data.get("price")
        if price is None:
            return
    except Exception:  # noqa: BLE001 - network/parse/quota failure - leave the last known value in place
        return

    prop.current_value = float(price)
    prop.current_value_updated_at = datetime.utcnow()
    _upsert_history_point(session, prop.id, date.today(), float(price), "estimate")
    session.commit()


def _upsert_history_point(session, property_id, event_date, amount, kind):
    existing = (
        session.query(PropertyValueHistory)
        .filter_by(property_id=property_id, event_date=event_date, kind=kind)
        .first()
    )
    if existing:
        existing.amount = amount
    else:
        session.add(PropertyValueHistory(property_id=property_id, event_date=event_date, amount=amount, kind=kind))


def refresh_value_history(prop, session):
    """Pulls real sale events + county tax assessments from RentCast's
    property-records endpoint into PropertyValueHistory - silently does
    nothing on any failure (missing key/address, stale check, monthly cap,
    network/parse error), same graceful-degradation shape as
    refresh_current_value(). Independent staleness check
    (value_history_synced_at / HISTORY_REFRESH_INTERVAL) and its own
    monthly-cap check, since this shares the same RentcastUsage counter as
    the AVM calls but on its own, much slower cadence."""
    if not Config.RENTCAST_API_KEY or not prop.address:
        return
    if prop.value_history_synced_at and datetime.utcnow() - prop.value_history_synced_at < HISTORY_REFRESH_INTERVAL:
        return
    if requests_used_this_month(session) >= MONTHLY_REQUEST_CAP:
        return

    _record_request(session)

    try:
        url = f"{RENTCAST_RECORDS_URL}?{urllib.parse.urlencode({'address': prop.address})}"
        request = urllib.request.Request(url, headers={"X-Api-Key": Config.RENTCAST_API_KEY})
        with urllib.request.urlopen(request, timeout=5) as response:
            records = json.loads(response.read())
        record = records[0] if records else None
    except Exception:  # noqa: BLE001 - network/parse/quota failure - leave existing history rows in place
        return

    if record:
        # `history` keys are event dates ("2021-09-17"), values carry their
        # own ISO datetime + price - only "Sale" events are a real dated
        # dollar amount comparable (loosely) to the AVM estimate; other
        # event types RentCast might add later are deliberately skipped
        # rather than guessed at.
        sale_dates_seen = set()
        for event in (record.get("history") or {}).values():
            if event.get("event") != "Sale" or event.get("price") is None or not event.get("date"):
                continue
            event_date = datetime.fromisoformat(event["date"].replace("Z", "+00:00")).date()
            sale_dates_seen.add(event_date)
            _upsert_history_point(session, prop.id, event_date, float(event["price"]), "sale")

        # Confirmed against the real API (2026-08-28): for some properties
        # (e.g. Brunswick) `history` comes back null entirely, but the most
        # recent sale is still available as top-level `lastSaleDate` /
        # `lastSalePrice` fields - without this fallback, those properties'
        # only real historical data point would be silently dropped.
        last_sale_date = record.get("lastSaleDate")
        last_sale_price = record.get("lastSalePrice")
        if last_sale_date and last_sale_price is not None:
            event_date = datetime.fromisoformat(last_sale_date.replace("Z", "+00:00")).date()
            if event_date not in sale_dates_seen:
                _upsert_history_point(session, prop.id, event_date, float(last_sale_price), "sale")

        # `taxAssessments` keys are year strings ("2022") - stored as
        # Jan 1 of that year, the same "precision is just a year" pattern
        # already used elsewhere in this schema (e.g. tax_report.year).
        for year_str, assessment in (record.get("taxAssessments") or {}).items():
            if assessment.get("value") is None:
                continue
            try:
                year = int(year_str)
            except ValueError:
                continue
            _upsert_history_point(session, prop.id, date(year, 1, 1), float(assessment["value"]), "tax_assessment")

    prop.value_history_synced_at = datetime.utcnow()
    session.commit()
