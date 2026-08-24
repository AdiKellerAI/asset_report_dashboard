from datetime import date

import pytest

from app.models import ExpenseType, MonthlyStatement, Mortgage, Property, Transaction, Transfer
from app.reports import (
    annual_yield_series,
    available_category_series,
    dashboard_breakdown,
    dashboard_summary,
    recent_noi_trend,
    resolve_period,
    trend_series,
)
from app.seed import seed


def test_resolve_period_this_month():
    start, end = resolve_period("this_month", today=date(2026, 8, 15))
    assert start == end == date(2026, 8, 1)


def test_resolve_period_this_year():
    start, end = resolve_period("this_year", today=date(2026, 8, 15))
    assert (start, end) == (date(2026, 1, 1), date(2026, 12, 1))


def test_resolve_period_custom_month():
    start, end = resolve_period("custom_month", month="2025-01")
    assert start == end == date(2025, 1, 1)


def test_resolve_period_custom_year():
    start, end = resolve_period("custom_year", year="2024")
    assert (start, end) == (date(2024, 1, 1), date(2024, 12, 1))


def test_resolve_period_all_time():
    assert resolve_period("all_time") == (None, None)


def test_resolve_period_unknown_raises():
    with pytest.raises(ValueError):
        resolve_period("next_tuesday")


def _property(db_session, nickname):
    return db_session.query(Property).filter_by(nickname=nickname).one()


def test_dashboard_summary_sums_across_properties_for_a_single_month(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    colburn = _property(db_session, "Colburn")
    month = date(2026, 5, 1)
    db_session.add_all(
        [
            MonthlyStatement(
                property_id=brunswick.id, month=month, gross_income=1000, total_operating_expense=200, noi=800
            ),
            MonthlyStatement(
                property_id=colburn.id, month=month, gross_income=500, total_operating_expense=100, noi=400
            ),
        ]
    )
    db_session.commit()

    result = dashboard_summary(db_session, property_nickname="all", period="custom_month", month="2026-05")

    assert result["gross_rent"] == pytest.approx(1500.0)
    assert result["total_expenses"] == pytest.approx(300.0)
    assert result["noi"] == pytest.approx(1200.0)
    assert result["has_data"] is True


def test_dashboard_summary_property_filter_narrows_to_one_property(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    colburn = _property(db_session, "Colburn")
    month = date(2026, 5, 1)
    db_session.add_all(
        [
            MonthlyStatement(property_id=brunswick.id, month=month, gross_income=1000, noi=800),
            MonthlyStatement(property_id=colburn.id, month=month, gross_income=500, noi=400),
        ]
    )
    db_session.commit()

    result = dashboard_summary(db_session, property_nickname="Brunswick", period="custom_month", month="2026-05")

    assert result["gross_rent"] == pytest.approx(1000.0)
    assert result["noi"] == pytest.approx(800.0)


def test_dashboard_summary_no_data_for_period_is_a_clean_empty_state(db_session):
    seed(db_session)

    result = dashboard_summary(db_session, property_nickname="all", period="custom_month", month="2020-01")

    assert result["has_data"] is False
    assert result["gross_rent"] == 0
    assert result["net_to_adi"] == 0


def test_net_to_adi_uses_latest_month_unpaid_bills_not_a_sum(db_session):
    """unpaid_bills is a snapshot of currently-outstanding bills, not a
    monthly flow - the same $1314 unpaid bill showing up unchanged across
    consecutive real months (see docs/PROJECT_STATUS.md) would be
    double-counted if summed across a multi-month period."""
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    db_session.add_all(
        [
            MonthlyStatement(
                property_id=brunswick.id, month=date(2026, 4, 1), noi=1000, unpaid_bills=-300
            ),
            MonthlyStatement(
                property_id=brunswick.id, month=date(2026, 5, 1), noi=1000, unpaid_bills=-300  # same unpaid bill, still outstanding
            ),
        ]
    )
    db_session.commit()

    result = dashboard_summary(db_session, property_nickname="Brunswick", period="custom_year", year="2026")

    # NOI summed (2000) + only ONE month's unpaid_bills (-300), not -600
    assert result["net_to_adi"] == pytest.approx(1700.0)


def test_net_to_adi_subtracts_mortgage_per_month_present_for_all_properties(db_session):
    """The mortgage is one combined loan for the whole portfolio (Adi
    confirmed 2026-08-23), not per property - it only ever affects the "all
    properties" Net Cash Flow, never an individual property's own column."""
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    db_session.add(Mortgage(monthly_payment=250))
    db_session.add_all(
        [
            MonthlyStatement(property_id=brunswick.id, month=date(2026, 1, 1), noi=1000),
            MonthlyStatement(property_id=brunswick.id, month=date(2026, 2, 1), noi=1000),
        ]
    )
    db_session.commit()

    all_result = dashboard_summary(db_session, property_nickname="all", period="custom_year", year="2026")
    brunswick_result = dashboard_summary(db_session, property_nickname="Brunswick", period="custom_year", year="2026")

    assert all_result["net_to_adi"] == pytest.approx(2000.0 - 250 * 2)
    assert brunswick_result["net_to_adi"] == pytest.approx(2000.0)  # mortgage NOT subtracted here


def test_accumulated_balance_is_portfolio_wide_regardless_of_property_filter(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    colburn = _property(db_session, "Colburn")
    db_session.add_all(
        [
            MonthlyStatement(property_id=brunswick.id, month=date(2026, 6, 1), net_owner_funds=1000),
            MonthlyStatement(property_id=colburn.id, month=date(2026, 6, 1), net_owner_funds=500),
        ]
    )
    db_session.commit()

    all_result = dashboard_summary(db_session, property_nickname="all", period="all_time")
    brunswick_only = dashboard_summary(db_session, property_nickname="Brunswick", period="all_time")

    assert all_result["accumulated_balance"] == pytest.approx(1500.0)
    assert brunswick_only["accumulated_balance"] == pytest.approx(1500.0)


def test_accumulated_balance_subtracts_transfers_sent_after_latest_statement(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 6, 1), net_owner_funds=1000))
    db_session.add(Transfer(transfer_date=date(2026, 7, 15), amount_sent=400, fee=30))
    db_session.add(Transfer(transfer_date=date(2026, 5, 1), amount_sent=999, fee=0))  # before cutoff, ignored
    db_session.commit()

    result = dashboard_summary(db_session, property_nickname="all", period="all_time")

    assert result["accumulated_balance"] == pytest.approx(1000.0 - 430.0)


def test_available_category_series_excludes_rent_income(db_session):
    seed(db_session)

    categories = available_category_series(db_session)

    assert "cat:rent_income" not in categories
    assert categories["cat:management_fee"] == "Management Fee"


def test_trend_series_one_point_per_month_no_cross_month_aggregation(db_session):
    """Unlike dashboard_summary, unpaid_bills/net_owner_funds don't need the
    latest-month-only treatment here - every chart point is exactly one
    month, so summing per month (not across months) is correct as-is."""
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    db_session.add_all(
        [
            MonthlyStatement(
                property_id=brunswick.id, month=date(2026, 4, 1), gross_income=1000, noi=800, unpaid_bills=-300
            ),
            MonthlyStatement(
                property_id=brunswick.id, month=date(2026, 5, 1), gross_income=1100, noi=900, unpaid_bills=-300
            ),
        ]
    )
    db_session.commit()

    result = trend_series(db_session, property_nickname="Brunswick", series_keys=["gross_rent", "noi", "unpaid_bills"])

    assert result["months"] == [date(2026, 4, 1), date(2026, 5, 1)]
    assert result["series"]["gross_rent"]["values"] == [1000.0, 1100.0]
    assert result["series"]["noi"]["values"] == [800.0, 900.0]
    assert result["series"]["unpaid_bills"]["values"] == [-300.0, -300.0]  # not doubled/summed


def test_trend_series_net_to_adi_per_month_with_mortgage(db_session):
    """Same portfolio-level-mortgage rule as dashboard_summary: only the
    "all properties" net_to_adi line subtracts it."""
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    db_session.add(Mortgage(monthly_payment=200))
    db_session.add_all(
        [
            MonthlyStatement(property_id=brunswick.id, month=date(2026, 4, 1), noi=1000, unpaid_bills=-50),
            MonthlyStatement(property_id=brunswick.id, month=date(2026, 5, 1), noi=1200, unpaid_bills=-100),
        ]
    )
    db_session.commit()

    all_result = trend_series(db_session, property_nickname="all", series_keys=["net_to_adi"])
    brunswick_result = trend_series(db_session, property_nickname="Brunswick", series_keys=["net_to_adi"])

    assert all_result["series"]["net_to_adi"]["values"] == pytest.approx([1000 - 50 - 200, 1200 - 100 - 200])
    assert brunswick_result["series"]["net_to_adi"]["values"] == pytest.approx([950, 1100])  # no mortgage here


def test_trend_series_category_line(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    management_fee = db_session.query(ExpenseType).filter_by(code="management_fee").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 4, 1)))
    db_session.add(
        Transaction(
            property_id=brunswick.id,
            expense_type_id=management_fee.id,
            date=date(2026, 4, 5),
            amount=125,
            description="Management Fees",
        )
    )
    db_session.commit()

    result = trend_series(db_session, property_nickname="Brunswick", series_keys=["cat:management_fee"])

    assert result["series"]["cat:management_fee"]["label"] == "Management Fee"
    assert result["series"]["cat:management_fee"]["values"] == [125.0]


def test_trend_series_defaults_to_gross_rent_noi_net_to_adi(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 4, 1), gross_income=100, noi=50))
    db_session.commit()

    result = trend_series(db_session, property_nickname="Brunswick")

    assert set(result["series"].keys()) == {"gross_rent", "noi", "net_to_adi"}


def test_trend_series_months_limit_keeps_only_the_most_recent(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    for m in [3, 4, 5, 6, 7]:
        db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, m, 1), gross_income=100 * m))
    db_session.commit()

    result = trend_series(db_session, property_nickname="Brunswick", series_keys=["gross_rent"], months_limit=2)

    assert result["months"] == [date(2026, 6, 1), date(2026, 7, 1)]
    assert result["series"]["gross_rent"]["values"] == [600.0, 700.0]


def test_dashboard_summary_this_month_defaults_to_latest_report_not_calendar_today(db_session):
    """The real calendar's current month rarely has a report yet (statements
    lag) - "This Month" without an explicit `today` should mean the latest
    month we actually have a monthly_statement for, not date.today()."""
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), gross_income=500, noi=300))
    db_session.commit()

    result = dashboard_summary(db_session, property_nickname="Brunswick", period="this_month")

    assert result["period_label"] == "July 2026"
    assert result["gross_rent"] == pytest.approx(500.0)
    assert result["has_data"] is True


def test_recent_noi_trend_returns_last_n_months_per_property_and_total(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    colburn = _property(db_session, "Colburn")
    for i, m in enumerate([3, 4, 5, 6, 7, 8]):
        db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, m, 1), noi=100 * (i + 1)))
        db_session.add(MonthlyStatement(property_id=colburn.id, month=date(2026, m, 1), noi=10 * (i + 1)))
    db_session.commit()

    result = recent_noi_trend(db_session, months=5)

    assert result["months"] == [date(2026, m, 1) for m in [4, 5, 6, 7, 8]]
    assert result["lines"]["Brunswick"] == [200.0, 300.0, 400.0, 500.0, 600.0]
    assert result["lines"]["Colburn"] == [20.0, 30.0, 40.0, 50.0, 60.0]
    assert result["lines"]["Total"] == [220.0, 330.0, 440.0, 550.0, 660.0]


def test_annual_yield_series_divides_annual_noi_by_property_value(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    colburn = _property(db_session, "Colburn")
    brunswick.value = 100_000
    colburn.value = 50_000
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2025, 6, 1), noi=5_000))
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2025, 12, 1), noi=5_000))
    db_session.add(MonthlyStatement(property_id=colburn.id, month=date(2025, 6, 1), noi=2_500))
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 3, 1), noi=3_000))
    db_session.commit()

    result = annual_yield_series(db_session)

    assert result["years"] == [2025, 2026]
    assert result["lines"]["Brunswick"] == pytest.approx([10.0, 3.0])  # 10000/100000, 3000/100000
    assert result["lines"]["Colburn"] == pytest.approx([5.0, 0.0])  # 2500/50000, no 2026 data yet
    # Total = combined NOI / combined value (150000)
    assert result["lines"]["Total"] == pytest.approx([(10_000 + 2_500) / 1500, 3_000 / 1500])


def test_annual_yield_series_skips_properties_with_no_value_set(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    colburn = _property(db_session, "Colburn")
    brunswick.value = 100_000
    # Colburn.value left None - hasn't been entered yet
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 1, 1), noi=1_000))
    db_session.add(MonthlyStatement(property_id=colburn.id, month=date(2026, 1, 1), noi=500))
    db_session.commit()

    result = annual_yield_series(db_session)

    assert "Brunswick" in result["lines"]
    assert "Colburn" not in result["lines"]
    # Total only reflects the valued property, not a silently-wrong blend
    assert result["lines"]["Total"] == pytest.approx([1.0])  # 1000/100000, Colburn excluded


def test_dashboard_breakdown_gives_per_property_and_total_for_same_period(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    colburn = _property(db_session, "Colburn")
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), gross_income=1000, noi=800))
    db_session.add(MonthlyStatement(property_id=colburn.id, month=date(2026, 7, 1), gross_income=500, noi=400))
    db_session.commit()

    result = dashboard_breakdown(db_session, period="this_month")

    by_nickname = {p["nickname"]: p for p in result["properties"]}
    assert by_nickname["Brunswick"]["gross_rent"] == pytest.approx(1000.0)
    assert by_nickname["Colburn"]["gross_rent"] == pytest.approx(500.0)
    assert result["total"]["gross_rent"] == pytest.approx(1500.0)
    assert result["total"]["period_label"] == "July 2026"
