from flask import Flask

from app.config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    from app.routes.health import health_bp
    app.register_blueprint(health_bp)

    return app
