"""Auto-fetched current property value estimate (RentCast's AVM API, by
address) - Adi's request, 2026-08-27: show today's value next to the
purchase price on /manage.

Cached in the DB (Property.current_value / current_value_updated_at), not
in memory like app/fx.py's exchange rate - this app runs on Vercel's
serverless platform, where an in-memory cache resets on every cold start,
which would blow through RentCast's free-tier 50-requests/month cap fast
for no reason. Refreshed lazily on a /manage visit once the stored value
is stale enough - 36h, not 24h, to keep 2 properties' roughly-daily
refreshes comfortably under that cap over a full month (2 properties x 1
refresh/36h is ~40 requests/month, vs. ~60/month at a strict 24h). There's
no background scheduler in this app, so "once a day" is approximated as
"whenever someone next opens Manage after 36h have passed" - the same
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
from app.models import RentcastUsage

RENTCAST_VALUE_URL = "https://api.rentcast.io/v1/avm/value"
REFRESH_INTERVAL = timedelta(hours=36)
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
    session.commit()
