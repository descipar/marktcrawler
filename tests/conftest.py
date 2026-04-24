"""pytest-Fixtures für alle Tests."""

import sys
import os
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
