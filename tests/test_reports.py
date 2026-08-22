from datetime import date

import pytest

from app.models import MonthlyStatement, Mortgage, Property, Transfer
from app.reports import dashboard_summary, resolve_period
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


def test_net_to_adi_subtracts_mortgage_per_month_present(db_session):
    seed(db_session)
    brunswick = _property(db_session, "Brunswick")
    db_session.add(Mortgage(property_id=brunswick.id, monthly_payment=250))
    db_session.add_all(
        [
            MonthlyStatement(property_id=brunswick.id, month=date(2026, 1, 1), noi=1000),
            MonthlyStatement(property_id=brunswick.id, month=date(2026, 2, 1), noi=1000),
        ]
    )
    db_session.commit()

    result = dashboard_summary(db_session, property_nickname="Brunswick", period="custom_year", year="2026")

    assert result["net_to_adi"] == pytest.approx(2000.0 - 250 * 2)


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
