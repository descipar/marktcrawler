"""Flask App Factory."""

import logging
import os
import secrets
from flask import Flask

from .database import init_db


def create_app() -> Flask:
    app = Flask(__name__)
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        secret_key = secrets.token_hex(32)
        logging.getLogger(__name__).warning(
            "SECRET_KEY nicht gesetzt – zufälliger Key wird verwendet. "
            "Sessions gehen bei Neustart verloren. Setze SECRET_KEY in .env."
        )
    app.secret_key = secret_key

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
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        from .scheduler import init_scheduler
        init_scheduler(app)

    return app
