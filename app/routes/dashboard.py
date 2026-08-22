from flask import Blueprint, render_template, request

from app.db import SessionLocal
from app.models import Property
from app.reports import PERIOD_CHOICES, dashboard_summary

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def landing():
    property_filter = request.args.get("property", "all")
    period = request.args.get("period", "this_month")
    month = request.args.get("month")
    year = request.args.get("year")

    if period not in PERIOD_CHOICES:
        period = "this_month"

    session = SessionLocal()
    try:
        properties = session.query(Property).order_by(Property.nickname).all()
        summary = dashboard_summary(session, property_filter, period, month=month, year=year)
    finally:
        session.close()

    return render_template(
        "dashboard.html",
        summary=summary,
        properties=properties,
        selected_property=property_filter,
        selected_period=period,
        selected_month=month or "",
        selected_year=year or "",
    )
