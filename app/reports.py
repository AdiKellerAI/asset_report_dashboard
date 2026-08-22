"""Landing-page aggregation (dev-plan.md sec 5.1): the 4 headline cards +
Accumulated Balance, computed from monthly_statement/mortgage/transfer - no
raw transaction scanning needed, since monthly_statement already carries the
per-month totals the ingestion pipeline derived from the categorized log.
"""

from datetime import date

from app.models import Mortgage, MonthlyStatement, Property, Transfer

PERIOD_CHOICES = ("this_month", "this_year", "custom_month", "custom_year", "all_time")


def resolve_period(period, month=None, year=None, today=None):
    """Return (start_month, end_month) - both inclusive, first-of-month dates -
    or (None, None) for all_time (no date filter)."""
    today = today or date.today()

    if period == "this_month":
        start = today.replace(day=1)
        return start, start
    if period == "this_year":
        return date(today.year, 1, 1), date(today.year, 12, 1)
    if period == "custom_month":
        year_part, month_part = (int(x) for x in month.split("-"))
        start = date(year_part, month_part, 1)
        return start, start
    if period == "custom_year":
        y = int(year)
        return date(y, 1, 1), date(y, 12, 1)
    if period == "all_time":
        return None, None
    raise ValueError(f"unknown period: {period!r}")


def period_label(period, start, end):
    if period == "all_time":
        return "All Time"
    if start == end:
        return start.strftime("%B %Y")
    return str(start.year)


def dashboard_summary(session, property_nickname="all", period="this_month", month=None, year=None, today=None):
    start, end = resolve_period(period, month=month, year=year, today=today)

    properties = session.query(Property).all()
    if property_nickname and property_nickname != "all":
        properties = [p for p in properties if p.nickname == property_nickname]
    property_ids = [p.id for p in properties]

    query = session.query(MonthlyStatement).filter(MonthlyStatement.property_id.in_(property_ids))
    if start is not None:
        query = query.filter(MonthlyStatement.month >= start, MonthlyStatement.month <= end)
    statements = query.all()

    gross_rent = sum(float(s.gross_income or 0) for s in statements)
    total_expenses = sum(float(s.total_operating_expense or 0) for s in statements)
    noi = sum(float(s.noi or 0) for s in statements)

    # unpaid_bills is a snapshot of currently-outstanding bills, not a monthly
    # flow (the same running-balance lesson as net_owner_funds, dev-plan.md
    # sec 14) - summing it across months in a multi-month period would
    # double-count the same still-unpaid amount. Use only the most recent
    # month actually present in range.
    months_present = {s.month for s in statements}
    latest_month = max(months_present, default=None)
    unpaid_bills = sum(float(s.unpaid_bills or 0) for s in statements if s.month == latest_month)

    mortgages = session.query(Mortgage).filter(Mortgage.property_id.in_(property_ids)).all()
    monthly_mortgage_total = sum(float(m.monthly_payment or 0) for m in mortgages)
    net_to_adi = noi + unpaid_bills - monthly_mortgage_total * len(months_present)

    return {
        "gross_rent": gross_rent,
        "total_expenses": total_expenses,
        "noi": noi,
        "net_to_adi": net_to_adi,
        "accumulated_balance": _accumulated_balance(session),
        "has_data": bool(statements),
        "period_start": start,
        "period_end": end,
        "period_label": period_label(period, start, end),
    }


def _accumulated_balance(session):
    """dev-plan.md sec 14 corrected formula: for each property, its most
    recent monthly_statement.net_owner_funds, summed across the portfolio,
    minus any transfer.amount_sent + fee sent after that point. Always
    portfolio-wide and as-of-now - not affected by the property/period
    filters (`transfer` is portfolio-level, not per-property, and this card
    answers "what's still with Overland right now," not a per-period question).
    """
    total = 0.0
    latest_months = []
    for prop in session.query(Property).all():
        latest = (
            session.query(MonthlyStatement)
            .filter_by(property_id=prop.id)
            .order_by(MonthlyStatement.month.desc())
            .first()
        )
        if latest is not None and latest.net_owner_funds is not None:
            total += float(latest.net_owner_funds)
            latest_months.append(latest.month)

    if latest_months:
        cutoff = max(latest_months)
        transfers = session.query(Transfer).filter(Transfer.transfer_date > cutoff).all()
        total -= sum(float(t.amount_sent) + float(t.fee) for t in transfers)

    return total
