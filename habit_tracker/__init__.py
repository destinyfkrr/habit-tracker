from pathlib import Path

from flask import Flask

from . import db
from .views import bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY="local-habit-tracker-secret",
        DATABASE=str(instance_path / "habit_tracker.sqlite3"),
    )

    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.init_db()
        from . import services

        services.seed_demo_data()

    app.register_blueprint(bp)

    @app.context_processor
    def inject_globals():
        from datetime import date

        return {"today_iso": date.today().isoformat()}

    return app
