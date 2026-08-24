from flask import Blueprint, g, render_template, request

from app.cache import get_or_set
from app.db import SessionLocal
from app.i18n import translate
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
        breakdown = get_or_set(
            ("dashboard_breakdown", period, month, year),
            lambda: dashboard_breakdown(session, period, month=month, year=year),
        )
        noi_trend = get_or_set(("recent_noi_trend", 6), lambda: recent_noi_trend(session, months=6))
        yield_series = get_or_set(
            ("annual_yield_series", yield_range),
            lambda: annual_yield_series(session, years_limit=YIELD_RANGE_CHOICES[yield_range]),
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
        total_label=translate("Total", g.lang),
    )
