from pathlib import Path

from flask import Flask

from .routes import bp as main_bp


def create_app():
    base_dir = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(base_dir / "templates"),
        static_folder=str(base_dir / "static"),
    )
    app.config["SECRET_KEY"] = "dog_playgrounds_secret"
    app.register_blueprint(main_bp)
    return app
