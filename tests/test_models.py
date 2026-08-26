from datetime import date

import pytest

from app.models import ExpenseType, MonthlyStatement, MortgagePayment, Property, Transaction, Transfer
from app.seed import EXPENSE_TYPES, PROPERTIES, seed


def test_seed_creates_properties_and_expense_types(db_session):
    seed(db_session)

    nicknames = {p.nickname for p in db_session.query(Property).all()}
    codes = {e.code for e in db_session.query(ExpenseType).all()}

    assert nicknames == set(PROPERTIES)
    assert codes == {code for code, _, _, _ in EXPENSE_TYPES}
    assert "owner_payment" not in codes

    non_operating = {
        e.code for e in db_session.query(ExpenseType).all() if not e.is_operating
    }
    assert non_operating == {"internal_transfer", "security_deposit_transfer", "owner_distribution"}


def test_seed_is_idempotent(db_session):
    seed(db_session)
    seed(db_session)

    assert db_session.query(Property).count() == len(PROPERTIES)
    assert db_session.query(ExpenseType).count() == len(EXPENSE_TYPES)


def test_transaction_round_trip(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    management_fee = db_session.query(ExpenseType).filter_by(code="management_fee").one()

    db_session.add(
        Transaction(
            property_id=brunswick.id,
            expense_type_id=management_fee.id,
            date=date(2026, 5, 1),
            amount=125.50,
            description="May management fee",
        )
    )
    db_session.commit()

    stored = db_session.query(Transaction).one()
    assert stored.property.nickname == "Brunswick"
    assert stored.expense_type.code == "management_fee"
    assert float(stored.amount) == 125.50


def test_monthly_statement_unique_per_property_and_month(db_session):
    seed(db_session)
    colburn = db_session.query(Property).filter_by(nickname="Colburn").one()

    db_session.add(MonthlyStatement(property_id=colburn.id, month=date(2026, 5, 1), net_owner_funds=900))
    db_session.commit()

    db_session.add(MonthlyStatement(property_id=colburn.id, month=date(2026, 5, 1), net_owner_funds=950))
    with pytest.raises(Exception):
        db_session.commit()


def test_mortgage_payment_round_trip_and_unique_per_month(db_session):
    db_session.add(
        MortgagePayment(
            month=date(2026, 9, 1),
            principal_amount=613.50,
            interest_amount=1092.78,
            total_payment=1706.28,
            remaining_balance=217420.01,
        )
    )
    db_session.commit()

    stored = db_session.query(MortgagePayment).one()
    assert float(stored.total_payment) == 1706.28
    assert float(stored.remaining_balance) == 217420.01

    db_session.add(MortgagePayment(month=date(2026, 9, 1), principal_amount=0, interest_amount=0, total_payment=0))
    with pytest.raises(Exception):
        db_session.commit()


def test_transfer_is_not_tied_to_a_property(db_session):
    db_session.add(Transfer(transfer_date=date(2026, 6, 1), amount_sent=2000, fee=30, note="first transfer in a while"))
    db_session.commit()

    stored = db_session.query(Transfer).one()
    assert float(stored.amount_sent) == 2000
    assert float(stored.fee) == 30
