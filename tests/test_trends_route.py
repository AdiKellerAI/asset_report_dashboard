import json
import re
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


def test_trends_page_defaults_to_last_1_year_range(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/trends")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="1y" selected' in body


def test_trends_page_range_limits_months_shown(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    for m in range(1, 15):  # 14 months of history
        month = date(2025, m, 1) if m <= 12 else date(2026, m - 12, 1)
        db_session.add(MonthlyStatement(property_id=brunswick.id, month=month, gross_income=100))
    db_session.commit()

    client = create_app().test_client()
    six_month_body = client.get("/trends?range=6m").get_data(as_text=True)
    all_time_body = client.get("/trends?range=all").get_data(as_text=True)

    def months_shown(body):
        match = re.search(r"const months = (\[[^\]]*\]);", body)
        return json.loads(match.group(1))

    assert 'value="6m" selected' in six_month_body
    assert len(months_shown(six_month_body)) == 6
    assert 'value="all" selected' in all_time_body
    assert len(months_shown(all_time_body)) == 14


def test_trends_page_falls_back_to_default_range_for_invalid_value(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/trends?range=not_a_real_range")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="1y" selected' in body
