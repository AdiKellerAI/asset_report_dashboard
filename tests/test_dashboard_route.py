from datetime import date

from app import create_app
from app.models import MonthlyStatement, Property
from app.seed import seed


def test_landing_page_renders_default_filters(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Gross Rent Collected" in body
    assert "Net to Adi" in body
    assert "Accumulated Balance" in body


def test_landing_page_reflects_property_and_period_filters(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 5, 1), gross_income=1234.56))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/?property=Brunswick&period=custom_month&month=2026-05")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "1234.56" in body
    assert 'value="Brunswick" selected' in body


def test_landing_page_falls_back_to_this_month_for_an_invalid_period(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/?period=not_a_real_period")

    assert response.status_code == 200
