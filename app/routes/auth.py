from datetime import datetime

import webauthn
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.db import SessionLocal
from app.models import WebauthnCredential

auth_bp = Blueprint("auth", __name__)

# Single-user app (no `user` table anywhere in this schema) - passkeys are
# discoverable/resident credentials, so this handle is never looked up
# anywhere, it just needs to be a stable constant per the WebAuthn spec.
WEBAUTHN_USER_ID = b"adi"


def _rp_id():
    return request.host.split(":")[0]


@auth_bp.get("/login")
def login_form():
    if session.get("authed"):
        return redirect("/")
    db_session = SessionLocal()
    try:
        has_passkeys = db_session.query(WebauthnCredential).count() > 0
    finally:
        db_session.close()
    return render_template("login.html", error=False, has_passkeys=has_passkeys)


@auth_bp.post("/login")
def login_submit():
    if request.form.get("password") == current_app.config["APP_PASSWORD"]:
        session["authed"] = True
        return redirect(request.args.get("next") or "/")
    return render_template("login.html", error=True), 401


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_form"))


# The two "begin/finish register" and "begin/finish login" pairs below are
# the standard WebAuthn ceremony shape: "begin" hands the browser a
# server-generated challenge to sign, "finish" verifies what came back.
# Registering a new passkey requires an existing session (enforced by the
# global `require_login` before_request hook in app/__init__.py, same as
# every other non-allowlisted route) - only login/begin and login/finish
# are allowlisted there to work *without* a session, since that's how you
# get one.


@auth_bp.post("/webauthn/register/begin")
def webauthn_register_begin():
    db_session = SessionLocal()
    try:
        existing = db_session.query(WebauthnCredential).all()
        options = webauthn.generate_registration_options(
            rp_id=_rp_id(),
            rp_name="Asset Report Dashboard",
            user_id=WEBAUTHN_USER_ID,
            user_name="adi",
            user_display_name="Adi Keller",
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=webauthn.base64url_to_bytes(c.credential_id)) for c in existing
            ],
        )
    finally:
        db_session.close()

    session["webauthn_reg_challenge"] = webauthn.helpers.bytes_to_base64url(options.challenge)
    return webauthn.options_to_json(options), 200, {"Content-Type": "application/json"}


@auth_bp.post("/webauthn/register/finish")
def webauthn_register_finish():
    challenge = session.pop("webauthn_reg_challenge", None)
    if not challenge:
        return jsonify(error="no registration in progress"), 400

    body = request.get_json(force=True)
    label = (body.pop("label", None) or "").strip() or None

    try:
        verification = webauthn.verify_registration_response(
            credential=body,
            expected_challenge=webauthn.base64url_to_bytes(challenge),
            expected_rp_id=_rp_id(),
            expected_origin=request.url_root.rstrip("/"),
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001 - any verification failure is a rejected enrollment, not a crash
        return jsonify(error=str(exc)), 400

    db_session = SessionLocal()
    try:
        db_session.add(
            WebauthnCredential(
                credential_id=webauthn.helpers.bytes_to_base64url(verification.credential_id),
                public_key=webauthn.helpers.bytes_to_base64url(verification.credential_public_key),
                sign_count=verification.sign_count,
                device_label=label,
            )
        )
        db_session.commit()
    finally:
        db_session.close()

    return jsonify(ok=True)


@auth_bp.post("/webauthn/login/begin")
def webauthn_login_begin():
    db_session = SessionLocal()
    try:
        has_passkeys = db_session.query(WebauthnCredential).count() > 0
    finally:
        db_session.close()

    if not has_passkeys:
        return jsonify(error="no passkeys registered"), 400

    options = webauthn.generate_authentication_options(
        rp_id=_rp_id(),
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    session["webauthn_auth_challenge"] = webauthn.helpers.bytes_to_base64url(options.challenge)
    return webauthn.options_to_json(options), 200, {"Content-Type": "application/json"}


@auth_bp.post("/webauthn/login/finish")
def webauthn_login_finish():
    challenge = session.pop("webauthn_auth_challenge", None)
    if not challenge:
        return jsonify(error="no login in progress"), 400

    body = request.get_json(force=True)
    credential_id = body.get("id")

    db_session = SessionLocal()
    try:
        row = db_session.query(WebauthnCredential).filter_by(credential_id=credential_id).one_or_none()
        if row is None:
            return jsonify(error="unknown passkey"), 400

        try:
            verification = webauthn.verify_authentication_response(
                credential=body,
                expected_challenge=webauthn.base64url_to_bytes(challenge),
                expected_rp_id=_rp_id(),
                expected_origin=request.url_root.rstrip("/"),
                credential_public_key=webauthn.base64url_to_bytes(row.public_key),
                credential_current_sign_count=row.sign_count,
                require_user_verification=True,
            )
        except Exception as exc:  # noqa: BLE001 - any verification failure is a rejected login, not a crash
            return jsonify(error=str(exc)), 400

        row.sign_count = verification.new_sign_count
        row.last_used_at = datetime.utcnow()
        db_session.commit()
    finally:
        db_session.close()

    session["authed"] = True
    return jsonify(redirect=request.args.get("next") or "/")
