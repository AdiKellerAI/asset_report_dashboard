from flask import Blueprint, redirect, request

language_bp = Blueprint("language", __name__)


@language_bp.get("/set-language/<lang>")
def set_language(lang):
    """Text language only - independent of currency (Adi's request,
    2026-08-24: two separate buttons, not one combined toggle). A real
    redirect (not a client-side toggle) since translating every string
    needs a fresh server render, not a live DOM patch."""
    if lang not in ("en", "he"):
        lang = "en"
    response = redirect(request.referrer or "/")
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response


@language_bp.get("/set-currency/<currency>")
def set_currency(currency):
    """Display currency only - independent of language."""
    if currency not in ("usd", "nis"):
        currency = "usd"
    response = redirect(request.referrer or "/")
    response.set_cookie("currency", currency, max_age=60 * 60 * 24 * 365)
    return response
