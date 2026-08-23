from flask import Flask, g, request

from app.config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    from app.routes.dashboard import dashboard_bp
    from app.routes.health import health_bp
    from app.routes.language import language_bp
    from app.routes.manage import manage_bp
    from app.routes.trends import trends_bp
    from app.routes.upload import upload_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(language_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(trends_bp)
    app.register_blueprint(upload_bp)

    @app.before_request
    def set_language_context():
        # The currency toggle also flips the whole site to Hebrew/RTL (a
        # single "lang" cookie drives both - see app/routes/language.py) -
        # read once per request rather than threading it through every
        # route/render_template call.
        lang = request.cookies.get("lang", "en")
        g.lang = lang if lang in ("en", "he") else "en"
        g.dir = "rtl" if g.lang == "he" else "ltr"

    @app.context_processor
    def inject_globals():
        from app.fx import get_usd_to_ils_rate

        return {"lang": g.lang, "dir": g.dir, "usd_to_ils_rate": get_usd_to_ils_rate()}

    @app.template_filter("t")
    def translate_filter(text):
        from app.i18n import translate

        return translate(text, g.lang)

    @app.template_filter("money")
    def money_filter(value):
        """1234.5 -> "1,234.50 $" (or, in Hebrew mode, the NIS equivalent
        with a ₪ suffix) - Adi's preferred format (currency symbol as a
        suffix, comma thousands separator). Storage/math everywhere else
        stays USD-only (dev-plan.md sec 15); this is purely a display
        conversion, and the whole page (not just numbers) is in the same
        language/currency mode since it's a real page render, not a
        client-side toggle."""
        from app.fx import get_usd_to_ils_rate

        value = float(value)
        if g.lang == "he":
            value = value * get_usd_to_ils_rate()
            return f"{value:,.2f} ₪"
        return f"{value:,.2f} $"

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
