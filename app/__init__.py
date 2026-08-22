from flask import Flask

from app.config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    from app.routes.health import health_bp
    from app.routes.upload import upload_bp
    app.register_blueprint(health_bp)
    app.register_blueprint(upload_bp)

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
