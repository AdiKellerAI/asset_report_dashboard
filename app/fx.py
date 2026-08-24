"""USD -> ILS display-only exchange rate (dev-plan.md sec 15): storage and
all math stay USD-only everywhere - this only feeds the site-wide currency
toggle. Cached once per calendar day so a page load doesn't hit the external
API every time; falls back to the last known (or a static approximate) rate
if the lookup fails, so a network hiccup never breaks the page.

Uses open.er-api.com (exchangerate-api.com's free tier, no key required,
refreshes once a day) rather than frankfurter.app - frankfurter sources ECB
rates, which only update on ECB business days, so it lags stale over
weekends/holidays instead of reflecting "today's" rate as Adi wants.
"""

import json
import urllib.request
from datetime import date

FX_API_URL = "https://open.er-api.com/v6/latest/USD"
FALLBACK_RATE = 3.7  # a reasonable static approximation, used only if no rate has ever been fetched

_cache = {"day": None, "rate": None}


def get_usd_to_ils_rate():
    today = date.today()
    if _cache["day"] == today and _cache["rate"] is not None:
        return _cache["rate"]

    try:
        with urllib.request.urlopen(FX_API_URL, timeout=3) as response:
            data = json.loads(response.read())
        rate = float(data["rates"]["ILS"])
    except Exception:  # noqa: BLE001 - any network/parse failure falls back, never breaks the page
        rate = _cache["rate"] or FALLBACK_RATE

    _cache["day"] = today
    _cache["rate"] = rate
    return rate


def format_money(value, currency):
    """Shared by the `money` Jinja filter and anywhere else (the tables
    page) that needs the same USD/NIS display formatting outside a
    template. `currency` is independent of the text language (Adi's
    request, 2026-08-24: two separate buttons, not one combined toggle)."""
    value = float(value)
    if currency == "nis":
        value = value * get_usd_to_ils_rate()
        return f"{value:,.2f} ₪"
    return f"{value:,.2f} $"
