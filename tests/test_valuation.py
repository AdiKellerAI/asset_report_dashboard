import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from app import valuation
from app.models import Property, PropertyValueHistory, RentcastUsage


def _property(db_session, address="123 Main St, Anytown, OH 12345"):
    prop = Property(nickname="Test", address=address)
    db_session.add(prop)
    db_session.commit()
    return prop


def _fake_response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__.return_value = response
    return response


def test_refresh_current_value_skips_without_an_api_key(db_session):
    prop = _property(db_session)

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = ""
        with patch("app.valuation.urllib.request.urlopen") as mock_urlopen:
            valuation.refresh_current_value(prop, db_session)

    mock_urlopen.assert_not_called()
    assert prop.current_value is None


def test_refresh_current_value_skips_a_property_with_no_address(db_session):
    prop = _property(db_session, address=None)

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen") as mock_urlopen:
            valuation.refresh_current_value(prop, db_session)

    mock_urlopen.assert_not_called()


def test_refresh_current_value_skips_when_recently_updated(db_session):
    prop = _property(db_session)
    prop.current_value = 100000
    prop.current_value_updated_at = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen") as mock_urlopen:
            valuation.refresh_current_value(prop, db_session)

    mock_urlopen.assert_not_called()
    assert float(prop.current_value) == 100000


def test_refresh_current_value_fetches_when_stale(db_session):
    prop = _property(db_session)
    prop.current_value = 100000
    prop.current_value_updated_at = datetime.utcnow() - timedelta(hours=50)
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", return_value=_fake_response({"price": 215000})):
            valuation.refresh_current_value(prop, db_session)

    assert float(prop.current_value) == 215000
    assert prop.current_value_updated_at is not None
    assert datetime.utcnow() - prop.current_value_updated_at < timedelta(seconds=5)


def test_refresh_current_value_fetches_when_never_fetched_before(db_session):
    prop = _property(db_session)
    assert prop.current_value_updated_at is None

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", return_value=_fake_response({"price": 150000})):
            valuation.refresh_current_value(prop, db_session)

    assert float(prop.current_value) == 150000


def test_refresh_current_value_leaves_last_known_value_on_failure(db_session):
    prop = _property(db_session)
    prop.current_value = 100000
    prop.current_value_updated_at = datetime.utcnow() - timedelta(hours=50)
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", side_effect=OSError("no network")):
            valuation.refresh_current_value(prop, db_session)

    assert float(prop.current_value) == 100000


def test_refresh_current_value_records_a_request_even_on_failure(db_session):
    """Conservative on purpose - a call that reached RentCast's server but
    errored may still count against their quota, so it counts against ours
    too rather than risk silently overshooting the real cap."""
    prop = _property(db_session)

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", side_effect=OSError("no network")):
            valuation.refresh_current_value(prop, db_session)

    assert valuation.requests_used_this_month(db_session) == 1


def test_refresh_current_value_refuses_once_the_monthly_cap_is_reached(db_session):
    prop = _property(db_session)
    db_session.add(RentcastUsage(year_month=valuation._current_month_key(), request_count=valuation.MONTHLY_REQUEST_CAP))
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen") as mock_urlopen:
            valuation.refresh_current_value(prop, db_session)

    mock_urlopen.assert_not_called()
    assert prop.current_value is None


def test_requests_used_this_month_counts_across_multiple_properties(db_session):
    brunswick = _property(db_session, address="1 Brunswick Ave, Anytown, OH 12345")
    colburn = Property(nickname="Colburn2", address="2 Colburn Ave, Anytown, OH 12345")
    db_session.add(colburn)
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", return_value=_fake_response({"price": 100000})):
            valuation.refresh_current_value(brunswick, db_session)
            valuation.refresh_current_value(colburn, db_session)

    assert valuation.requests_used_this_month(db_session) == 2


def test_refresh_current_value_also_records_an_estimate_history_point(db_session):
    prop = _property(db_session)

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", return_value=_fake_response({"price": 150000})):
            valuation.refresh_current_value(prop, db_session)

    point = db_session.query(PropertyValueHistory).filter_by(property_id=prop.id, kind="estimate").one()
    assert point.event_date == date.today()
    assert float(point.amount) == 150000


def test_refresh_value_history_skips_without_an_api_key(db_session):
    prop = _property(db_session)

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = ""
        with patch("app.valuation.urllib.request.urlopen") as mock_urlopen:
            valuation.refresh_value_history(prop, db_session)

    mock_urlopen.assert_not_called()
    assert prop.value_history_synced_at is None


def test_refresh_value_history_skips_a_property_with_no_address(db_session):
    prop = _property(db_session, address=None)

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen") as mock_urlopen:
            valuation.refresh_value_history(prop, db_session)

    mock_urlopen.assert_not_called()


def test_refresh_value_history_skips_when_recently_synced(db_session):
    prop = _property(db_session)
    prop.value_history_synced_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen") as mock_urlopen:
            valuation.refresh_value_history(prop, db_session)

    mock_urlopen.assert_not_called()


def test_refresh_value_history_refuses_once_the_monthly_cap_is_reached(db_session):
    prop = _property(db_session)
    db_session.add(RentcastUsage(year_month=valuation._current_month_key(), request_count=valuation.MONTHLY_REQUEST_CAP))
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen") as mock_urlopen:
            valuation.refresh_value_history(prop, db_session)

    mock_urlopen.assert_not_called()
    assert prop.value_history_synced_at is None


def test_refresh_value_history_leaves_existing_rows_on_failure(db_session):
    prop = _property(db_session)
    prop.value_history_synced_at = datetime.utcnow() - timedelta(days=40)
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", side_effect=OSError("no network")):
            valuation.refresh_value_history(prop, db_session)

    assert db_session.query(PropertyValueHistory).filter_by(property_id=prop.id).count() == 0


def test_refresh_value_history_parses_sale_events_and_tax_assessments(db_session):
    """Colburn's real shape (confirmed against the live API, 2026-08-28):
    `history` has dated Sale events, `taxAssessments` has per-year values."""
    prop = _property(db_session)
    payload = [
        {
            "history": {
                "2007-02-01": {"event": "Sale", "date": "2007-02-01T00:00:00.000Z", "price": 69900},
                "2021-09-17": {"event": "Sale", "date": "2021-09-17T00:00:00.000Z", "price": 92500},
                "2015-06-01": {"event": "Listed", "date": "2015-06-01T00:00:00.000Z", "price": 80000},
            },
            "taxAssessments": {
                "2022": {"year": 2022, "value": 25520},
                "2024": {"year": 2024, "value": 32380},
            },
        }
    ]

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", return_value=_fake_response(payload)):
            valuation.refresh_value_history(prop, db_session)

    rows = {
        (r.event_date, r.kind): float(r.amount)
        for r in db_session.query(PropertyValueHistory).filter_by(property_id=prop.id).all()
    }
    assert rows == {
        (date(2007, 2, 1), "sale"): 69900,
        (date(2021, 9, 17), "sale"): 92500,
        (date(2022, 1, 1), "tax_assessment"): 25520,
        (date(2024, 1, 1), "tax_assessment"): 32380,
    }
    assert prop.value_history_synced_at is not None


def test_refresh_value_history_falls_back_to_last_sale_when_history_is_null(db_session):
    """Brunswick's real shape (confirmed against the live API, 2026-08-28):
    `history` and `taxAssessments` come back null, but the most recent sale
    is still available via top-level `lastSaleDate`/`lastSalePrice` -
    without this fallback, Brunswick's only real data point is silently
    dropped."""
    prop = _property(db_session)
    payload = [
        {
            "history": None,
            "taxAssessments": None,
            "lastSaleDate": "2021-12-13T00:00:00.000Z",
            "lastSalePrice": 61000,
        }
    ]

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", return_value=_fake_response(payload)):
            valuation.refresh_value_history(prop, db_session)

    point = db_session.query(PropertyValueHistory).filter_by(property_id=prop.id).one()
    assert point.event_date == date(2021, 12, 13)
    assert point.kind == "sale"
    assert float(point.amount) == 61000


def test_refresh_value_history_does_not_duplicate_a_sale_already_in_history(db_session):
    """lastSaleDate/lastSalePrice usually just repeats the most recent Sale
    event already present in `history` - the fallback must not double it up
    as a second, duplicate row for the same date."""
    prop = _property(db_session)
    payload = [
        {
            "history": {
                "2021-09-17": {"event": "Sale", "date": "2021-09-17T00:00:00.000Z", "price": 92500},
            },
            "taxAssessments": None,
            "lastSaleDate": "2021-09-17T00:00:00.000Z",
            "lastSalePrice": 92500,
        }
    ]

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", return_value=_fake_response(payload)):
            valuation.refresh_value_history(prop, db_session)

    assert db_session.query(PropertyValueHistory).filter_by(property_id=prop.id).count() == 1


def test_refresh_value_history_records_a_request_even_on_failure(db_session):
    prop = _property(db_session)

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", side_effect=OSError("no network")):
            valuation.refresh_value_history(prop, db_session)

    assert valuation.requests_used_this_month(db_session) == 1
