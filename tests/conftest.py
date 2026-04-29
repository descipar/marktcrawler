"""pytest-Fixtures für alle Tests."""

import os
import sys
import threading
from pathlib import Path

# Projektwurzel in sys.path eintragen, damit `app` gefunden wird
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """
    Richtet eine frische SQLite-Datenbank in einem temporären Verzeichnis ein.
    Wird für jeden Test neu erzeugt – keine Seiteneffekte zwischen Tests.
    """
    import app.database as db

    test_db_path = tmp_path / "test_baby_crawler.db"
    monkeypatch.setattr(db, "DB_PATH", test_db_path)
    db.init_db()
    yield db
    # tmp_path wird von pytest automatisch aufgeräumt


def _restore_env(key: str, original):
    if original is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = original


@pytest.fixture()
def live_server(tmp_path):
    """Flask-App mit vorbereiteter Test-DB in einem Background-Thread.

    Legt 35 Listings an (> PAGE_SIZE=30), damit Pagination-Tests greifen.
    Nach jedem Test wird der Server gestoppt und DB_PATH wiederhergestellt.
    """
    from werkzeug.serving import make_server
    import app.database as db_module
    from app.scrapers.base import Listing

    _orig_path = db_module.DB_PATH
    _orig_main = os.environ.get("WERKZEUG_RUN_MAIN")
    _orig_secret = os.environ.get("SECRET_KEY")
    srv = None

    try:
        db_module.DB_PATH = tmp_path / "ui_test.db"
        db_module.init_db()

        for i in range(35):
            db_module.save_listing(Listing(
                listing_id=f"ui-{i:04d}",
                platform="Kleinanzeigen",
                title=f"Kinderwagen Modell {i:04d}",
                price=f"{30 + i} €",
                location="München",
                url=f"https://example.com/item/{i}",
                search_term="kinderwagen",
            ))

        os.environ["WERKZEUG_RUN_MAIN"] = ""   # Scheduler nicht starten
        os.environ["SECRET_KEY"] = "ui-test-secret"

        from app import create_app
        flask_app = create_app()
        flask_app.config["TESTING"] = True

        srv = make_server("127.0.0.1", 0, flask_app)
        port = srv.socket.getsockname()[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        yield f"http://127.0.0.1:{port}"

    finally:
        if srv:
            srv.shutdown()
        db_module.DB_PATH = _orig_path
        _restore_env("WERKZEUG_RUN_MAIN", _orig_main)
        _restore_env("SECRET_KEY", _orig_secret)
