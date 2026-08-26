from flask import Flask, current_app, g, redirect, request, session
from jinja2 import pass_context

from app.config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    # Let the browser cache style.css etc. for real instead of revalidating
    # on every navigation (see the Cache-Control comment below) - an hour is
    # short enough that active CSS work still shows up on the next reload
    # after a deploy, long enough to skip the round trip for a whole session.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.data_browser import data_browser_bp
    from app.routes.health import health_bp
    from app.routes.language import language_bp
    from app.routes.manage import manage_bp
    from app.routes.report import report_bp
    from app.routes.trends import trends_bp
    from app.routes.upload import upload_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(data_browser_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(language_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(trends_bp)
    app.register_blueprint(upload_bp)

    # Pay Neon's serverless cold-start tax (a suspended compute waking up
    # can take several real seconds) and the exchange-rate API's first
    # network round trip HERE, once per process at startup, instead of on
    # whichever real request happens to land first (Adi's "very very slow"
    # report, 2026-08-24) - best-effort, since a failure here shouldn't
    # block the app from starting; the normal per-request paths (pool
    # pre-ping, fx-rate's own fallback) still handle a cold/failed warm-up
    # gracefully either way.
    try:
        from sqlalchemy import text

        from app.db import SessionLocal

        warm_session = SessionLocal()
        try:
            warm_session.execute(text("SELECT 1"))
        finally:
            warm_session.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.fx import get_usd_to_ils_rate

        get_usd_to_ils_rate()
    except Exception:  # noqa: BLE001
        pass

    @app.before_request
    def require_login():
        # Single shared-password gate (dev-plan.md sec 13.3) - a no-op
        # locally/in tests where APP_PASSWORD isn't set, so it only takes
        # effect once Adi configures it (e.g. on Vercel). /health stays open
        # for uptime checks.
        if not current_app.config["APP_PASSWORD"]:
            return None
        if request.path.startswith("/static/") or request.path in ("/login", "/health"):
            return None
        if not session.get("authed"):
            return redirect(f"/login?next={request.path}")
        return None

    @app.before_request
    def set_language_context():
        # Language (text) and currency (display) are two independent cookies
        # driving two independent header buttons (Adi's request, 2026-08-24 -
        # previously one combined toggle) - read both once per request rather
        # than threading them through every route/render_template call.
        # Layout direction deliberately stays LTR even in Hebrew (Adi's
        # request, 2026-08-23: translate the words, but never mirror the
        # page) - `dir` is kept as a template variable rather than removed
        # outright since some charts/inputs still opt out of it explicitly.
        lang = request.cookies.get("lang", "en")
        g.lang = lang if lang in ("en", "he") else "en"
        g.dir = "ltr"
        currency = request.cookies.get("currency", "usd")
        g.currency = currency if currency in ("usd", "nis") else "usd"

    @app.context_processor
    def inject_globals():
        from app.fx import get_usd_to_ils_rate

        return {
            "lang": g.lang,
            "dir": g.dir,
            "currency": g.currency,
            "usd_to_ils_rate": get_usd_to_ils_rate(),
            "auth_enabled": bool(current_app.config["APP_PASSWORD"]),
        }

    @app.template_filter("t")
    @pass_context
    def translate_filter(ctx, text):
        # `@pass_context` isn't for its own sake here (we don't read `ctx`) -
        # it's the only way to stop Jinja from constant-folding this filter.
        # Every call site is `{{ "some literal string"|t }}`, and Jinja's
        # compiler treats a filter applied to a literal as a pure function of
        # that literal: it evaluates it ONCE at template-compile time (the
        # template's first render in this process) and bakes the result into
        # the compiled bytecode forever after - which silently freezes the
        # whole site in whatever language happened to be active during that
        # first render, no matter what `g.lang` is on later requests. Marking
        # the filter as context-dependent tells Jinja it can't assume that,
        # so it re-evaluates on every render like `money` (applied to a
        # variable, never a literal, so it was never eligible for folding).
        from app.i18n import translate

        return translate(text, g.lang)

    @app.after_request
    def prevent_caching_of_language_dependent_pages(response):
        # Every page's HTML depends on the `lang`/`currency` cookies -
        # without this, some mobile browsers will serve a cached copy of "/"
        # from before a cookie changed instead of re-fetching, which looks
        # exactly like "switching to Hebrew didn't do anything". `no-cache`
        # (not `no-store`) is deliberate: it still forces a real round trip
        # every time (we send no ETag/Last-Modified, so there's nothing to
        # revalidate against - every request is a full fetch either way),
        # but unlike `no-store` it doesn't disable the mobile browser's
        # back/forward cache, which is what made every navigation flicker
        # (Adi's report, 2026-08-26) - `no-store` is one of the documented
        # conditions that unconditionally evicts a page from bfcache.
        #
        # Static assets (style.css etc.) don't depend on those cookies at
        # all, so this blanket rule was also forcing a fresh network round
        # trip for the stylesheet on every single navigation - real, avoidable
        # latency that leaves the outgoing page visible for longer while the
        # incoming one waits on its CSS, which reads as "a blink of the other
        # page" on a real network (Adi's report, 2026-08-26). Leaving Flask's
        # own static-file headers (SEND_FILE_MAX_AGE_DEFAULT below, plus its
        # built-in ETag) alone lets the browser skip that round trip entirely
        # on repeat visits instead.
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.template_filter("money")
    def money_filter(value):
        """1234.5 -> "1,234.50 $" (or, in NIS mode, the ILS equivalent with a
        ₪ suffix) - Adi's preferred format (currency symbol as a suffix,
        comma thousands separator). Storage/math everywhere else stays
        USD-only (dev-plan.md sec 15); this is purely a display conversion,
        independent of the text language (Adi's request, 2026-08-24), and
        it's a real page render (not a client-side toggle) so the whole
        page's numbers switch together."""
        from app.fx import format_money

        return format_money(value, g.currency)

    @app.cli.command("seed-db")
    def seed_db():
        """Seed the properties and expense-type taxonomy into Postgres."""
        from app.db import SessionLocal
        from app.seed import seed

        session = SessionLocal()
        try:
            seed(session)
        finally:
            session.close()

    @app.cli.command("recategorize-transactions")
    def recategorize_transactions_cmd():
        """Re-run categorize_transaction against already-ingested transactions
        and recompute the monthly_statement totals they feed - no PDF re-parse.
        See docs/PROJECT_STATUS.md's other_expense finding."""
        from app.db import SessionLocal
        from app.ingestion import recategorize_transactions

        session = SessionLocal()
        try:
            count = recategorize_transactions(session)
            print(f"Recategorized {count} transaction(s).")
        finally:
            session.close()

    return app
