from flask import Blueprint, g, render_template, request

from app.cache import get_or_set
from app.db import SessionLocal
from app.i18n import translate
from app.models import Property
from app.reports import (
    DEFAULT_RANGE,
    DEFAULT_TREND_SERIES,
    RANGE_CHOICES,
    SUMMARY_SERIES,
    available_category_series,
    trend_series,
)

trends_bp = Blueprint("trends", __name__)


@trends_bp.get("/trends")
def trends():
    property_filter = request.args.get("property", "all")
    selected_series = request.args.getlist("series") or DEFAULT_TREND_SERIES
    selected_range = request.args.get("range", DEFAULT_RANGE)
    if selected_range not in RANGE_CHOICES:
        selected_range = DEFAULT_RANGE

    session = SessionLocal()
    try:
        # Only trend_series() (a plain dict of primitives - months/labels/
        # floats) is cached here, not the ORM Property/ExpenseType rows
        # below - those stay a live per-request query so nothing risks
        # being read off a since-closed session on a later cache hit.
        properties = session.query(Property).order_by(Property.nickname).all()
        category_series = available_category_series(session)
        valid_keys = set(SUMMARY_SERIES) | set(category_series)
        selected_series = [k for k in selected_series if k in valid_keys] or DEFAULT_TREND_SERIES

        data = get_or_set(
            ("trend_series", property_filter, tuple(sorted(selected_series)), selected_range),
            lambda: trend_series(session, property_filter, selected_series, months_limit=RANGE_CHOICES[selected_range]),
        )
    finally:
        session.close()

    # Chart labels are embedded via |tojson (raw JS), bypassing the `t`
    # Jinja filter used everywhere else - translate them here instead.
    series = {key: {**value, "label": translate(value["label"], g.lang)} for key, value in data["series"].items()}

    return render_template(
        "trends.html",
        properties=properties,
        selected_property=property_filter,
        summary_series=SUMMARY_SERIES,
        category_series=category_series,
        selected_series=selected_series,
        selected_range=selected_range,
        months=[m.strftime("%Y-%m") for m in data["months"]],
        series=series,
    )
