from unittest.mock import patch

from app import fx


def test_get_usd_to_ils_rate_falls_back_when_lookup_fails():
    fx._cache["day"] = None
    fx._cache["rate"] = None

    with patch("app.fx.urllib.request.urlopen", side_effect=OSError("no network")):
        rate = fx.get_usd_to_ils_rate()

    assert rate == fx.FALLBACK_RATE


def test_get_usd_to_ils_rate_caches_for_the_day():
    fx._cache["day"] = None
    fx._cache["rate"] = None

    with patch("app.fx.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = OSError("no network")
        first = fx.get_usd_to_ils_rate()
        second = fx.get_usd_to_ils_rate()

    assert first == second
    mock_urlopen.assert_called_once()  # second call reused the cached (fallback) rate
