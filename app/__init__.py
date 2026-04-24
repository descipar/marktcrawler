"""Flask App Factory."""

import logging
from flask import Flask

from .database import init_db


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "baby-crawler-secret-2024"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Datenbank initialisieren
    init_db()

    # Routen registrieren
    from .routes import bp
    app.register_blueprint(bp)

    # Scheduler starten (nur einmal, nicht im Werkzeug-Reloader-Child)
    import os
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        from .scheduler import init_scheduler
        init_scheduler(app)

    return app
