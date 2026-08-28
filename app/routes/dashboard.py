from flask import Blueprint, g, render_template, request

from app.cache import get_or_set
from app.db import SessionLocal
from app.i18n import translate
from app.models import Property
from app.reports import (
    DEFAULT_YIELD_RANGE,
    PERIOD_CHOICES,
    YIELD_RANGE_CHOICES,
    annual_yield_series,
    dashboard_breakdown,
    recent_noi_trend,
)

dashboard_bp = Blueprint("dashboard", __name__)


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
        property_values = [
            {
                "nickname": p.nickname,
                "value": float(p.value) if p.value is not None else None,
                "current_value": float(p.current_value) if p.current_value is not None else None,
            }
            for p in get_properties()
        ]
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
        total_label=translate("Total", g.lang),
    )
