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


def test_landing_page_shows_both_properties_and_total_in_one_view(db_session):
    """No property filter - both assets and the combined total must be
    visible together, per Adi's request."""
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    colburn = db_session.query(Property).filter_by(nickname="Colburn").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 5, 1), gross_income=1000))
    db_session.add(MonthlyStatement(property_id=colburn.id, month=date(2026, 5, 1), gross_income=500))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/?period=custom_month&month=2026-05")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Brunswick" in body
    assert "Colburn" in body
    assert "Total" in body
    assert "1,000.00 $" in body  # Brunswick's own column
    assert "500.00 $" in body  # Colburn's own column
    assert "1,500.00 $" in body  # the combined Total column
    assert 'name="property"' not in body  # no property filter control anymore


def test_landing_page_falls_back_to_this_month_for_an_invalid_period(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/?period=not_a_real_period")

    assert response.status_code == 200


def test_landing_page_default_this_month_uses_latest_report_not_calendar_today(db_session):
    """Regression test: the default "This Month" view must reflect the
    latest actual report (e.g. July 2026), not real-world date.today(),
    which may be a month with no statement uploaded yet."""
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), gross_income=2000))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "July 2026" in body
    assert "no statement data for this period yet" not in body


def test_landing_page_includes_last_5_months_income_chart_per_property_and_total(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    for m in [3, 4, 5, 6, 7]:
        db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, m, 1), gross_income=100 * m))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="income-chart"' in body
    assert '"2026-07-01"' in body
    assert '"Brunswick"' in body
    assert '"Colburn"' in body
    assert '"Total"' in body
    assert "700.0" in body


def test_landing_page_money_format_uses_comma_and_dollar_suffix(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), net_owner_funds=15107.93))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/?period=custom_month&month=2026-07")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "15,107.93 $" in body
    assert "$15107.93" not in body


def test_landing_page_money_values_carry_raw_usd_for_the_currency_toggle(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), net_owner_funds=15107.93))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/?period=custom_month&month=2026-07")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'class="money" data-usd="15107.93"' in body
    assert 'id="currency-toggle"' in body
    assert "FX_RATE_USD_TO_ILS" in body
