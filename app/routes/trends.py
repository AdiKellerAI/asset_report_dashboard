from flask import Blueprint, render_template, request

from app.db import SessionLocal
from app.models import Property
from app.reports import DEFAULT_TREND_SERIES, SUMMARY_SERIES, available_category_series, trend_series

trends_bp = Blueprint("trends", __name__)


@trends_bp.get("/trends")
def trends():
    property_filter = request.args.get("property", "all")
    selected_series = request.args.getlist("series") or DEFAULT_TREND_SERIES

    session = SessionLocal()
    try:
        properties = session.query(Property).order_by(Property.nickname).all()
        category_series = available_category_series(session)
        valid_keys = set(SUMMARY_SERIES) | set(category_series)
        selected_series = [k for k in selected_series if k in valid_keys] or DEFAULT_TREND_SERIES

        data = trend_series(session, property_filter, selected_series)
    finally:
        session.close()

    return render_template(
        "trends.html",
        properties=properties,
        selected_property=property_filter,
        summary_series=SUMMARY_SERIES,
        category_series=category_series,
        selected_series=selected_series,
        months=[m.isoformat() for m in data["months"]],
        series=data["series"],
    )
