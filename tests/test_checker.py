"""Tests für app/checker.py: Verfügbarkeits-Check."""

import pytest
from unittest.mock import patch, MagicMock
from app.scrapers.base import Listing
import app.checker as checker_module


@pytest.fixture()
def db_with_listings(tmp_path, monkeypatch):
    import app.database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    listings = [
        Listing(platform="Test", title="Noch online", price="10 €",
                location="München", url="https://example.com/1",
                listing_id="online-1", search_term="test"),
        Listing(platform="Test", title="Nicht mehr da", price="20 €",
                location="München", url="https://example.com/2",
                listing_id="gone-1", search_term="test"),
        Listing(platform="Test", title="Favorit gelöscht", price="30 €",
                location="München", url="https://example.com/3",
                listing_id="gone-fav-1", search_term="test"),
    ]
    for l in listings:
        db.save_listing(l)

    fav_id = next(l["id"] for l in db.get_listings() if l["listing_id"] == "gone-fav-1")
    db.toggle_favorite(fav_id)

    # Anzeigen auf 2 Stunden alt setzen damit min_age_minutes-Filter greift
    import sqlite3
    conn = sqlite3.connect(str(db.DB_PATH))
    conn.execute("UPDATE listings SET found_at = datetime('now', '-120 minutes')")
    conn.commit()
    conn.close()

    return db


class TestRunAvailabilityCheck:

    def _mock_response(self, status_code: int):
        resp = MagicMock()
        resp.status_code = status_code
        return resp

    def test_404_wird_geloescht(self, db_with_listings):
        def fake_head(url, **kwargs):
            if "example.com/2" in url:
                return self._mock_response(404)
            return self._mock_response(200)

        with patch("app.checker.requests.head", side_effect=fake_head), \
             patch("app.checker.time.sleep"):
            result = checker_module.run_availability_check()

        assert result["deleted"] == 1
        ids = [l["listing_id"] for l in db_with_listings.get_listings()]
        assert "gone-1" not in ids
        assert "online-1" in ids

    def test_410_wird_geloescht(self, db_with_listings):
        def fake_head(url, **kwargs):
            if "example.com/2" in url:
                return self._mock_response(410)
            return self._mock_response(200)

        with patch("app.checker.requests.head", side_effect=fake_head), \
             patch("app.checker.time.sleep"):
            result = checker_module.run_availability_check()

        assert result["deleted"] == 1

    def test_favorit_wird_auch_geloescht(self, db_with_listings):
        def fake_head(url, **kwargs):
            if "example.com/3" in url:
                return self._mock_response(404)
            return self._mock_response(200)

        with patch("app.checker.requests.head", side_effect=fake_head), \
             patch("app.checker.time.sleep"):
            result = checker_module.run_availability_check()

        assert result["deleted"] == 1
        ids = [l["listing_id"] for l in db_with_listings.get_listings()]
        assert "gone-fav-1" not in ids

    def test_200_bleibt_erhalten(self, db_with_listings):
        with patch("app.checker.requests.head", return_value=self._mock_response(200)), \
             patch("app.checker.time.sleep"):
            result = checker_module.run_availability_check()

        assert result["deleted"] == 0
        assert db_with_listings.get_listing_count() == 3

    def test_403_wird_nicht_geloescht(self, db_with_listings):
        with patch("app.checker.requests.head", return_value=self._mock_response(403)), \
             patch("app.checker.time.sleep"):
            result = checker_module.run_availability_check()

        assert result["deleted"] == 0

    def test_netzwerkfehler_wird_ignoriert(self, db_with_listings):
        import requests as req_lib
        with patch("app.checker.requests.head",
                   side_effect=req_lib.exceptions.ConnectionError("Timeout")), \
             patch("app.checker.time.sleep"):
            result = checker_module.run_availability_check()

        assert result["deleted"] == 0
        assert result["errors"] == 3
        assert db_with_listings.get_listing_count() == 3

    def test_deaktiviert_ueberspringt_check(self, db_with_listings):
        db_with_listings.set_setting("availability_check_enabled", "0")
        with patch("app.checker.requests.head") as mock_head:
            result = checker_module.run_availability_check()

        mock_head.assert_not_called()
        assert result["status"] == "disabled"

    def test_gibt_statistiken_zurueck(self, db_with_listings):
        with patch("app.checker.requests.head", return_value=self._mock_response(200)), \
             patch("app.checker.time.sleep"):
            result = checker_module.run_availability_check()

        assert "checked" in result
        assert "deleted" in result
        assert "errors" in result
        assert result["checked"] == 3


class TestRunningGuard:

    def test_concurrent_check_wird_abgelehnt(self, db_with_listings):
        """Zweiter Aufruf während laufendem Check gibt already_running zurück."""
        import app.checker as chk

        # _running von außen auf True setzen (simuliert laufenden Check)
        with chk._lock:
            chk._running = True

        try:
            result = chk.run_availability_check()
            assert result["status"] == "already_running"
            assert result["checked"] == 0
        finally:
            with chk._lock:
                chk._running = False

    def test_is_running_false_initial(self):
        import app.checker as chk
        assert chk.is_running() is False


class TestDbAvailabilityFunctions:

    def test_get_all_listing_urls(self, db_with_listings):
        rows = db_with_listings.get_all_listing_urls()
        assert len(rows) == 3
        assert all("url" in r and "listing_id" in r and "title" in r for r in rows)

    def test_delete_listing_by_listing_id_normal(self, db_with_listings):
        db_with_listings.delete_listing_by_listing_id("online-1")
        ids = [l["listing_id"] for l in db_with_listings.get_listings()]
        assert "online-1" not in ids

    def test_delete_listing_by_listing_id_favorit(self, db_with_listings):
        """Favoriten werden ebenfalls gelöscht."""
        db_with_listings.delete_listing_by_listing_id("gone-fav-1")
        assert db_with_listings.get_listing_count() == 2

    def test_delete_unbekannte_id_kein_fehler(self, db_with_listings):
        db_with_listings.delete_listing_by_listing_id("existiert-nicht")
        assert db_with_listings.get_listing_count() == 3
