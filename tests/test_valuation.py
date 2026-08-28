import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app import valuation
from app.models import Property


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
    prop.current_value_updated_at = datetime.utcnow() - timedelta(hours=40)
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
    prop.current_value_updated_at = datetime.utcnow() - timedelta(hours=40)
    db_session.commit()

    with patch("app.valuation.Config") as mock_config:
        mock_config.RENTCAST_API_KEY = "fake-key"
        with patch("app.valuation.urllib.request.urlopen", side_effect=OSError("no network")):
            valuation.refresh_current_value(prop, db_session)

    assert float(prop.current_value) == 100000
