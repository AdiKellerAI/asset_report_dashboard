from datetime import date

from app import create_app
from app.models import ExpenseType, MonthlyStatement, Property, Transaction
from app.seed import seed


def test_report_page_renders_waterfall_for_latest_month(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    mgmt = db_session.query(ExpenseType).filter_by(code="management_fee").one()
    db_session.add(
        MonthlyStatement(
            property_id=brunswick.id, month=date(2026, 7, 1), gross_income=1460, total_operating_expense=146, noi=1314
        )
    )
    db_session.add(Transaction(property_id=brunswick.id, expense_type_id=mgmt.id, date=date(2026, 7, 6), amount=146))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/report")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Understand This Report" in body
    assert 'id="waterfall-chart"' in body
    assert "Management Fee" in body
    assert "Brunswick" in body


def test_report_page_can_select_a_specific_month_and_property(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 3, 1), gross_income=1460, noi=1000))
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), gross_income=1460, noi=500))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/report?property=Brunswick&month=2026-03")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "1,000.00 $" in body  # March's NOI, not July's


def test_report_page_shows_empty_state_for_a_month_with_no_data(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/report?month=2020-01")

    assert response.status_code == 200
    assert "No report data for this month yet." in response.get_data(as_text=True)
