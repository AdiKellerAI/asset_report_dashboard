from flask import Blueprint, redirect, request

language_bp = Blueprint("language", __name__)


@language_bp.get("/set-language/<lang>")
def set_language(lang):
    """The header's currency toggle: one cookie drives both language and
    currency together (Hebrew implies NIS, English implies USD) since Adi
    wants them to change as one unit. A real redirect (not a client-side
    toggle) since a full RTL layout flip needs a fresh server render, not
    a live DOM patch."""
    if lang not in ("en", "he"):
        lang = "en"
    response = redirect(request.referrer or "/")
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response
