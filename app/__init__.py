from flask import Flask, current_app, g, redirect, request, session
from jinja2 import pass_context

from app.config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.data_browser import data_browser_bp
    from app.routes.health import health_bp
    from app.routes.language import language_bp
    from app.routes.manage import manage_bp
    from app.routes.trends import trends_bp
    from app.routes.upload import upload_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(data_browser_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(language_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(trends_bp)
    app.register_blueprint(upload_bp)

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
        # The currency toggle also switches the whole site's text to Hebrew (a
        # single "lang" cookie drives both - see app/routes/language.py) -
        # read once per request rather than threading it through every
        # route/render_template call. Layout direction deliberately stays LTR
        # even in Hebrew (Adi's request, 2026-08-23: translate the words, but
        # never mirror the page) - `dir` is kept as a template variable rather
        # than removed outright since some charts/inputs still opt out of it
        # explicitly.
        lang = request.cookies.get("lang", "en")
        g.lang = lang if lang in ("en", "he") else "en"
        g.dir = "ltr"

    @app.context_processor
    def inject_globals():
        from app.fx import get_usd_to_ils_rate

        return {
            "lang": g.lang,
            "dir": g.dir,
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
        # Every page's HTML depends on the `lang` cookie - without an
        # explicit no-store, some mobile browsers will serve a cached copy of
        # "/" from before the cookie changed instead of re-fetching, which
        # looks exactly like "switching to Hebrew didn't do anything".
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.template_filter("money")
    def money_filter(value):
        """1234.5 -> "1,234.50 $" (or, in Hebrew mode, the NIS equivalent
        with a ₪ suffix) - Adi's preferred format (currency symbol as a
        suffix, comma thousands separator). Storage/math everywhere else
        stays USD-only (dev-plan.md sec 15); this is purely a display
        conversion, and the whole page (not just numbers) is in the same
        language/currency mode since it's a real page render, not a
        client-side toggle."""
        from app.fx import format_money

        return format_money(value, g.lang)

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
