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
"""

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from app.config import Config

RENTCAST_VALUE_URL = "https://api.rentcast.io/v1/avm/value"
REFRESH_INTERVAL = timedelta(hours=36)


def refresh_current_value(prop, session):
    """Updates `prop.current_value` / `current_value_updated_at` in place
    (and commits) if stale and an API key + address are available -
    silently leaves the existing (possibly still None) value alone on any
    failure, so a RentCast outage, an exhausted quota, or a missing key
    never breaks the Manage page."""
    if not Config.RENTCAST_API_KEY or not prop.address:
        return
    if prop.current_value_updated_at and datetime.utcnow() - prop.current_value_updated_at < REFRESH_INTERVAL:
        return

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
