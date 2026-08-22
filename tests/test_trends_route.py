from datetime import date

from app import create_app
from app.models import MonthlyStatement, Property
from app.seed import seed


def test_trends_page_defaults_to_gross_rent_noi_net_to_adi(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/trends")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="gross_rent" checked' in body
    assert 'value="noi" checked' in body
    assert 'value="net_to_adi" checked' in body
    assert 'value="total_expenses" checked' not in body


def test_trends_page_reflects_chosen_series_and_property(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 4, 1), reserve=-300))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/trends?property=Brunswick&series=reserve")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="Brunswick" selected' in body
    assert 'value="reserve" checked' in body
    assert "-300" in body


def test_trends_page_ignores_unknown_series_keys(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/trends?series=not_a_real_series")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    # falls back to the default 3 rather than rendering nothing
    assert 'value="gross_rent" checked' in body
