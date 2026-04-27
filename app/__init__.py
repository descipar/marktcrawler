"""Flask App Factory."""

import logging
import os
import secrets
from pathlib import Path
from flask import Flask

from .database import init_db

_SECRET_KEY_FILE = Path(os.environ.get("DATA_DIR", "/data")) / "secret_key.txt"


def _load_or_create_secret_key() -> str:
    """Liest den persistierten SECRET_KEY oder erstellt ihn einmalig.

    Q13-Fix: Ein zufällig generierter Key ohne Persistierung macht alle
    Sessions bei jedem Neustart ungültig (Nutzer werden ausgeloggt).
    """
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    try:
        if _SECRET_KEY_FILE.exists():
            key = _SECRET_KEY_FILE.read_text().strip()
            if key:
                return key
        key = secrets.token_hex(32)
        _SECRET_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SECRET_KEY_FILE.write_text(key)
        return key
    except OSError as e:
        logging.getLogger(__name__).warning(
            f"SECRET_KEY konnte nicht persistiert werden: {e}. "
            "Sessions gehen bei Neustart verloren."
        )
        return secrets.token_hex(32)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = _load_or_create_secret_key()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Log-Buffer für das Dashboard-Terminal registrieren
    from .logbuffer import handler as log_handler
    logging.getLogger().addHandler(log_handler)

    # Datenbank initialisieren
    init_db()

    # Routen registrieren
    from .routes import bp
    app.register_blueprint(bp)

    # Scheduler im Reloader-Child starten (der beantwortet Requests);
    # in Produktion (kein Reloader) immer starten.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        from .scheduler import init_scheduler
        init_scheduler(app)

    return app
