from datetime import date

from flask import Blueprint, render_template, request

from app.cache import get_or_set
from app.db import SessionLocal
from app.reports import available_report_months, latest_reported_month, properties_summary, report_breakdown

report_bp = Blueprint("report", __name__)


@report_bp.get("/report")
def report():
    property_filter = request.args.get("property", "all")

    session = SessionLocal()
    try:
        properties = get_or_set(("properties_summary",), lambda: properties_summary(session))
        if property_filter != "all" and property_filter not in [p["nickname"] for p in properties]:
            property_filter = "all"

        months = get_or_set(("available_report_months",), lambda: available_report_months(session))
        month_param = request.args.get("month")
        if month_param:
            year_part, month_part = month_param.split("-")
            selected_month = date(int(year_part), int(month_part), 1)
        else:
            selected_month = get_or_set(
                ("latest_reported_month",), lambda: latest_reported_month(session)
            ) or date.today().replace(day=1)

        breakdown = get_or_set(
            ("report_breakdown", selected_month.isoformat(), property_filter),
            lambda: report_breakdown(session, selected_month, property_filter),
        )
    finally:
        session.close()

    return render_template(
        "report.html",
        properties=properties,
        selected_property=property_filter,
        months=months,
        selected_month=selected_month,
        breakdown=breakdown,
    )
