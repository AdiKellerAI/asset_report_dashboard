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
    assert '<th scope="row">Balance</th>' in body
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


def test_landing_page_includes_last_5_months_noi_chart_per_property_and_total(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    for m in [3, 4, 5, 6, 7]:
        db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, m, 1), noi=100 * m))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="noi-chart"' in body
    assert '"2026-07"' in body
    assert '"2026-07-01"' not in body  # chart x-axis is month/year only, no day
    assert '"Brunswick"' in body
    assert '"Colburn"' in body
    assert '"Total"' in body
    assert "700.0" in body


def test_landing_page_shows_annual_yield_chart_when_property_values_are_set(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    brunswick.value = 96_500
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), noi=800))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Annual Yield" in body
    assert 'id="yield-chart"' in body
    assert '"Brunswick"' in body


def test_landing_page_shows_empty_state_for_annual_yield_when_no_values_set(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Annual Yield" in body
    assert 'id="yield-chart"' not in body
    assert "add them in Manage" in body


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


def test_landing_page_has_currency_toggle_defaulting_to_usd_english(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), net_owner_funds=15107.93))
    db_session.commit()

    client = create_app().test_client()
    response = client.get("/?period=custom_month&month=2026-07")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '15,107.93 $' in body
    assert 'class="currency-btn"' in body
    assert 'class="fx-rate-bar"' in body  # shown regardless of language, per Adi's request
    assert '<html lang="en" dir="ltr">' in body


def test_landing_page_lang_cookie_translates_text_but_leaves_currency_alone(db_session):
    """Language and currency are two independent cookies/buttons (Adi's
    request, 2026-08-24 - previously one combined toggle). Switching only the
    `lang` cookie translates every string, but money stays in USD until the
    separate `currency` cookie is also switched. Layout deliberately stays
    LTR throughout regardless (Adi's request, 2026-08-23: translate the
    words, never mirror the page)."""
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), net_owner_funds=15107.93))
    db_session.commit()

    client = create_app().test_client()
    client.set_cookie("lang", "he")
    response = client.get("/?period=custom_month&month=2026-07")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '<html lang="he" dir="ltr">' in body
    assert "15,107.93 $" in body  # still USD - currency cookie wasn't touched
    assert 'class="fx-rate-bar"' in body
    assert "בית" in body  # "Home" nav link, translated
    assert '<header class="page-header">' in body  # no dir override needed - the whole page stays LTR now
    assert "נטו (NOI)" in body  # "Net (NOI)" row header, translated


def test_landing_page_currency_cookie_converts_money_but_leaves_text_alone(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    db_session.add(MonthlyStatement(property_id=brunswick.id, month=date(2026, 7, 1), net_owner_funds=15107.93))
    db_session.commit()

    client = create_app().test_client()
    client.set_cookie("currency", "nis")
    response = client.get("/?period=custom_month&month=2026-07")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '<html lang="en" dir="ltr">' in body
    assert "15,107.93 $" not in body  # converted to NIS
    assert "₪" in body
    assert ">Home<" in body  # nav stays English - only currency switched


def test_set_language_route_sets_cookie_and_redirects():
    client = create_app().test_client()
    response = client.get("/set-language/he", headers={"Referer": "/trends"})

    assert response.status_code == 302
    assert response.headers["Location"] == "/trends"
    assert "lang=he" in response.headers.get("Set-Cookie", "")


def test_set_currency_route_sets_cookie_and_redirects():
    client = create_app().test_client()
    response = client.get("/set-currency/nis", headers={"Referer": "/trends"})

    assert response.status_code == 302
    assert response.headers["Location"] == "/trends"
    assert "currency=nis" in response.headers.get("Set-Cookie", "")
