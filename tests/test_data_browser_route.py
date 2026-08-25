from datetime import date

from app import create_app
from app.models import ExpenseType, MonthlyStatement, Property, Transaction
from app.seed import seed


def test_tables_page_defaults_to_transactions(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/tables")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="table-select"' in body
    assert '<option value="transaction" selected>' in body


def test_tables_page_shows_selected_table_rows(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    mgmt = db_session.query(ExpenseType).filter_by(code="management_fee").one()
    db_session.add(
        Transaction(
            property_id=brunswick.id,
            expense_type_id=mgmt.id,
            date=date(2026, 7, 1),
            amount=125,
            description="July management fee",
        )
    )
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/tables?table=transaction")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "July management fee" in body
    assert "125.00 $" in body


def test_tables_page_falls_back_to_default_table_for_unknown_name(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/tables?table=not_a_real_table")

    assert response.status_code == 200
    assert '<option value="transaction" selected>' in response.get_data(as_text=True)


def test_table_rows_endpoint_paginates(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    for m in range(1, 6):
        db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, m, 1), gross_income=100 * m))
    db_session.commit()

    client = create_app().test_client()
    first_page = client.get("/tables/monthly_statement/rows?offset=0&limit=2").get_json()
    second_page = client.get("/tables/monthly_statement/rows?offset=2&limit=2").get_json()

    assert first_page["total"] == 5
    assert len(first_page["rows"]) == 2
    assert first_page["has_more"] is True
    assert "Gross Income" in first_page["headers"]  # switching tables client-side needs the new headers too
    assert len(second_page["rows"]) == 2
    assert second_page["has_more"] is True


def test_table_rows_endpoint_rejects_unknown_table(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/tables/not_a_real_table/rows")

    assert response.status_code == 404
