import re

from flask import Blueprint, g, render_template, request

from app.cache import get_or_set
from app.db import SessionLocal
from app.i18n import translate
from app.models import Property, PropertyValueHistory
from app.reports import (
    DEFAULT_YIELD_RANGE,
    PERIOD_CHOICES,
    YIELD_RANGE_CHOICES,
    annual_yield_series,
    dashboard_breakdown,
    recent_noi_trend,
)

dashboard_bp = Blueprint("dashboard", __name__)


def _zillow_search_url(address):
    """Zillow's own documented "search by address" URL pattern - not an
    API, just a plain link a human clicks (Adi's request, 2026-08-28: a
    link below the Property Values table to cross-check the RentCast
    estimate). Couldn't verify this resolves correctly via an automated
    fetch - Zillow blocks non-browser requests (a 403 even on a plain
    WebFetch) - but works fine for an actual browser click; worth a
    one-time manual check that it lands on the right property."""
    if not address:
        return None
    slug = re.sub(r"[^A-Za-z0-9\s-]", "", address)
    slug = re.sub(r"\s+", "-", slug.strip())
    return f"https://www.zillow.com/homes/{slug}_rb/"


def _property_value_dict(p):
    value = float(p.value) if p.value is not None else None
    current_value = float(p.current_value) if p.current_value is not None else None
    change_pct = (current_value - value) / value * 100 if value and current_value is not None else None
    return {
        "nickname": p.nickname,
        "value": value,
        "current_value": current_value,
        "change_pct": change_pct,
        "zillow_url": _zillow_search_url(p.address),
    }


def _property_value_history_series(session, properties):
    """A "price per year" graph from the real, sparse data in
    PropertyValueHistory (sale events, county tax assessments, and this
    app's own RentCast AVM estimates over time) - Adi's request,
    2026-08-28: "the whole price history of these 2 assets ... show graph
    with the assets price per year", built with what's actually known
    rather than a smoothed/interpolated guess (Adi confirmed this
    approach via AskUserQuestion after seeing how sparse and asymmetric
    the two properties' real RentCast data is - Brunswick has exactly one
    data point, its 2021 sale).

    Returns None when there's no history yet at all (e.g. right after this
    feature first deploys, before any /manage visit has triggered a
    refresh_value_history() sync) so the template can hide the chart
    section entirely rather than render an empty one.
    """
    rows = (
        session.query(PropertyValueHistory)
        .filter(PropertyValueHistory.property_id.in_([p.id for p in properties]))
        .order_by(PropertyValueHistory.event_date)
        .all()
    )
    if not rows:
        return None

    nickname_by_id = {p.id: p.nickname for p in properties}
    # (nickname, kind) -> {year: amount} - multiple rows for the same
    # property/kind/year (e.g. two AVM estimates fetched months apart in
    # the same year) collapse to the latest one chronologically, since
    # `rows` is already ordered by event_date and a later dict assignment
    # for the same key just overwrites the earlier one.
    points = {}
    years = set()
    for row in rows:
        nickname = nickname_by_id.get(row.property_id)
        if nickname is None:
            continue
        year = row.event_date.year
        years.add(year)
        points.setdefault((nickname, row.kind), {})[year] = float(row.amount)

    years = sorted(years)
    series = [
        {"property": nickname, "kind": kind, "values": [values.get(year) for year in years]}
        for (nickname, kind), values in points.items()
    ]
    # Stable order (grouped by property, then a fixed kind order) so the
    # legend and the template's per-property color assignment stay
    # deterministic across requests, rather than depending on dict
    # iteration order.
    kind_order = {"sale": 0, "estimate": 1, "tax_assessment": 2}
    nickname_order = {p.nickname: i for i, p in enumerate(properties)}
    series.sort(key=lambda s: (nickname_order.get(s["property"], 0), kind_order.get(s["kind"], 99)))

    return {"years": years, "series": series}


@dashboard_bp.get("/")
def landing():
    period = request.args.get("period", "this_month")
    month = request.args.get("month")
    year = request.args.get("year")

    if period not in PERIOD_CHOICES:
        period = "this_month"

    yield_range = request.args.get("yield_range", DEFAULT_YIELD_RANGE)
    if yield_range not in YIELD_RANGE_CHOICES:
        yield_range = DEFAULT_YIELD_RANGE

    session = SessionLocal()
    try:
        # Shared across the 3 calls below instead of each independently
        # re-querying the same 2-row properties table (a real, measured
        # contributor to "the site is very very slow", 2026-08-25 - every
        # one of these is a remote Neon round trip). Lazy + memoized: only
        # fetched at all if at least one of the 3 below actually misses its
        # cache, and at most once even then - a fully-warm hit costs zero
        # extra queries, same as before this fix.
        properties_holder = {}

        def get_properties():
            if "v" not in properties_holder:
                properties_holder["v"] = session.query(Property).order_by(Property.nickname).all()
            return properties_holder["v"]

        breakdown = get_or_set(
            ("dashboard_breakdown", period, month, year),
            lambda: dashboard_breakdown(session, period, month=month, year=year, properties=get_properties()),
        )
        noi_trend = get_or_set(
            ("recent_noi_trend", 6), lambda: recent_noi_trend(session, months=6, properties=get_properties())
        )
        yield_series = get_or_set(
            ("annual_yield_series", yield_range),
            lambda: annual_yield_series(
                session, years_limit=YIELD_RANGE_CHOICES[yield_range], properties=get_properties()
            ),
        )
        # Purchase price + auto-fetched current value, below the Annual
        # Yield chart (Adi's request, 2026-08-28) - reuses get_properties()
        # (already fetched/memoized for the 3 calls above, live ORM rows,
        # not the cached properties_summary() which doesn't carry these
        # two fields) rather than an extra query. Display-only here - the
        # actual RentCast refresh only happens on a /manage visit (see
        # app/routes/manage.py), so visiting Home never triggers a call or
        # counts against the monthly cap.
        property_values = [_property_value_dict(p) for p in get_properties()]
        property_history = get_or_set(
            ("property_value_history",),
            lambda: _property_value_history_series(session, get_properties()),
        )
    finally:
        session.close()

    return render_template(
        "dashboard.html",
        properties=breakdown["properties"],
        total=breakdown["total"],
        selected_period=period,
        selected_month=month or "",
        selected_year=year or "",
        noi_months=[m.strftime("%Y-%m") for m in noi_trend["months"]],
        noi_lines=noi_trend["lines"],
        selected_yield_range=yield_range,
        yield_years=yield_series["years"],
        yield_lines=yield_series["lines"],
        property_values=property_values,
        property_history=property_history,
        total_label=translate("Total", g.lang),
    )
