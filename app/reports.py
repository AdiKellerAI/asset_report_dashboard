"""Landing-page aggregation (dev-plan.md sec 5.1): the 4 headline cards +
Accumulated Balance, computed from monthly_statement/mortgage/transfer - no
raw transaction scanning needed, since monthly_statement already carries the
per-month totals the ingestion pipeline derived from the categorized log.
"""

from datetime import date

from app.models import ExpenseType, Mortgage, MonthlyStatement, Property, Transaction, Transfer

PERIOD_CHOICES = ("this_month", "this_year", "custom_month", "custom_year", "all_time")

# The trends page's selectable "summary" series (dev-plan.md sec 5.1's trend
# chart, generalized to every monthly_statement figure, per Adi's request).
# rent_income is deliberately not duplicated here as a category series - it's
# the same number as gross_rent.
SUMMARY_SERIES = {
    "gross_rent": "Gross Rent Collected",
    "total_expenses": "Total Property Expenses",
    "noi": "Net Operating Income",
    "net_to_adi": "Net to Adi",
    "net_owner_funds": "Net Owner Funds",
    "beginning_balance": "Beginning Balance",
    "ending_balance": "Ending Balance",
    "unpaid_bills": "Unpaid Bills",
    "reserve": "Property Reserve",
}

DEFAULT_TREND_SERIES = ["gross_rent", "noi", "net_to_adi"]

_DIRECT_STATEMENT_FIELDS = {"net_owner_funds", "beginning_balance", "ending_balance", "reserve", "unpaid_bills"}


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
    property_ids = _property_ids_for(session, property_nickname)

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


def available_category_series(session):
    """Every expense_type as a selectable trends-page line, except
    rent_income - that's the same number as the gross_rent summary series."""
    return {
        f"cat:{e.code}": e.label
        for e in session.query(ExpenseType).filter(ExpenseType.code != "rent_income").order_by(ExpenseType.label).all()
    }


def _property_ids_for(session, property_nickname):
    properties = session.query(Property).all()
    if property_nickname and property_nickname != "all":
        properties = [p for p in properties if p.nickname == property_nickname]
    return [p.id for p in properties]


def trend_series(session, property_nickname="all", series_keys=None):
    """One data point per month, across every month with a monthly_statement
    row in scope - unlike dashboard_summary, there's no cross-month
    aggregation here, so the unpaid_bills/net_owner_funds running-balance
    caveat doesn't apply: each chart point is exactly one month's value."""
    series_keys = series_keys or DEFAULT_TREND_SERIES
    property_ids = _property_ids_for(session, property_nickname)

    statements = (
        session.query(MonthlyStatement)
        .filter(MonthlyStatement.property_id.in_(property_ids))
        .order_by(MonthlyStatement.month)
        .all()
    )
    by_month = {}
    for s in statements:
        by_month.setdefault(s.month, []).append(s)
    months = sorted(by_month.keys())

    monthly_mortgage_total = sum(
        float(m.monthly_payment or 0)
        for m in session.query(Mortgage).filter(Mortgage.property_id.in_(property_ids)).all()
    )

    category_codes = [k.split(":", 1)[1] for k in series_keys if k.startswith("cat:")]
    category_totals = {}
    if category_codes:
        txns = (
            session.query(Transaction.date, ExpenseType.code, Transaction.amount)
            .join(ExpenseType, ExpenseType.id == Transaction.expense_type_id)
            .filter(Transaction.property_id.in_(property_ids), ExpenseType.code.in_(category_codes))
            .all()
        )
        for txn_date, code, amount in txns:
            month_key = txn_date.replace(day=1)
            category_totals.setdefault(code, {})
            category_totals[code][month_key] = category_totals[code].get(month_key, 0.0) + float(amount)

    category_labels = available_category_series(session)

    result = {}
    for key in series_keys:
        if key.startswith("cat:"):
            code = key.split(":", 1)[1]
            result[key] = {
                "label": category_labels.get(key, code),
                "values": [category_totals.get(code, {}).get(m, 0.0) for m in months],
            }
            continue

        label = SUMMARY_SERIES.get(key, key)
        values = []
        for m in months:
            stmts = by_month[m]
            if key == "gross_rent":
                values.append(sum(float(s.gross_income or 0) for s in stmts))
            elif key == "total_expenses":
                values.append(sum(float(s.total_operating_expense or 0) for s in stmts))
            elif key == "noi":
                values.append(sum(float(s.noi or 0) for s in stmts))
            elif key == "net_to_adi":
                noi_total = sum(float(s.noi or 0) for s in stmts)
                unpaid_total = sum(float(s.unpaid_bills or 0) for s in stmts)
                values.append(noi_total + unpaid_total - monthly_mortgage_total)
            elif key in _DIRECT_STATEMENT_FIELDS:
                values.append(sum(float(getattr(s, key) or 0) for s in stmts))
            else:
                values.append(0.0)
        result[key] = {"label": label, "values": values}

    return {"months": months, "series": result}
