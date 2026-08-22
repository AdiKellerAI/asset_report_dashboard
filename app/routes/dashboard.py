from flask import Blueprint, render_template, request

from app.db import SessionLocal
from app.reports import PERIOD_CHOICES, dashboard_breakdown, recent_noi_trend

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def landing():
    period = request.args.get("period", "this_month")
    month = request.args.get("month")
    year = request.args.get("year")

    if period not in PERIOD_CHOICES:
        period = "this_month"

    session = SessionLocal()
    try:
        breakdown = dashboard_breakdown(session, period, month=month, year=year)
        noi_trend = recent_noi_trend(session, months=5)
    finally:
        session.close()

    return render_template(
        "dashboard.html",
        properties=breakdown["properties"],
        total=breakdown["total"],
        selected_period=period,
        selected_month=month or "",
        selected_year=year or "",
        noi_months=[m.isoformat() for m in noi_trend["months"]],
        noi_lines=noi_trend["lines"],
    )
