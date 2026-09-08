from app import create_app
from app.config import Config
from app.models import WebauthnCredential


class _PasswordConfig(Config):
    APP_PASSWORD = "testpass"


def _add_credential(db_session, credential_id="cred-1", label="Test Device"):
    cred = WebauthnCredential(
        credential_id=credential_id, public_key="fake-public-key", sign_count=0, device_label=label
    )
    db_session.add(cred)
    db_session.commit()
    return cred


def test_login_begin_returns_400_when_no_passkeys_registered(db_session):
    client = create_app().test_client()
    response = client.post("/webauthn/login/begin")

    assert response.status_code == 400


def test_login_begin_returns_options_once_a_passkey_exists(db_session):
    _add_credential(db_session)

    client = create_app().test_client()
    response = client.post("/webauthn/login/begin")

    assert response.status_code == 200
    body = response.get_json()
    assert "challenge" in body
    assert body["allowCredentials"] == []  # discoverable/usernameless flow


def test_login_page_only_shows_passkey_button_once_one_is_registered(db_session):
    client = create_app().test_client()
    body = client.get("/login").get_data(as_text=True)
    assert "passkey-login-btn" not in body

    _add_credential(db_session)

    body = create_app().test_client().get("/login").get_data(as_text=True)
    assert "passkey-login-btn" in body


def test_register_begin_requires_an_existing_session_when_password_is_set():
    client = create_app(_PasswordConfig).test_client()
    response = client.post("/webauthn/register/begin")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_register_begin_works_once_logged_in(db_session):
    client = create_app(_PasswordConfig).test_client()
    client.post("/login", data={"password": "testpass"})

    response = client.post("/webauthn/register/begin")

    assert response.status_code == 200
    body = response.get_json()
    assert body["authenticatorSelection"]["residentKey"] == "required"


def test_manage_delete_webauthn_credential(db_session):
    cred = _add_credential(db_session)

    client = create_app().test_client()
    response = client.post(f"/manage/webauthn/{cred.id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert "Passkey removed" in response.get_data(as_text=True)
    assert db_session.query(WebauthnCredential).filter_by(id=cred.id).one_or_none() is None
