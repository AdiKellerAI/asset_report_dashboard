from flask import Flask

from app.config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    from app.routes.health import health_bp
    app.register_blueprint(health_bp)

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

    return app
