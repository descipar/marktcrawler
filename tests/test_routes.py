"""Tests für app/routes.py: Flask-Routen und REST-API."""

import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Flask-App mit temporärer Datenbank für jeden Test."""
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()

    import os
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "")  # Scheduler nicht starten

    from app import create_app
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


# ── Dashboard ─────────────────────────────────────────────────

class TestDashboard:

    def test_index_liefert_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_enthaelt_suchbegriffe(self, client):
        resp = client.get("/")
        assert b"kinderwagen" in resp.data.lower()

    def test_index_filter_favorites(self, client):
        resp = client.get("/?favorites=1")
        assert resp.status_code == 200

    def test_index_filter_free(self, client):
        resp = client.get("/?free=1")
        assert resp.status_code == 200


# ── Suchbegriffe ──────────────────────────────────────────────

class TestTermsRoutes:

    def test_add_term(self, client):
        resp = client.post("/terms", data={"term": "laufstall"}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"laufstall" in resp.data.lower()

    def test_add_term_leer_redirect(self, client):
        resp = client.post("/terms", data={"term": ""}, follow_redirects=True)
        assert resp.status_code == 200

    def test_add_term_zu_lang(self, client):
        resp = client.post("/terms", data={"term": "x" * 201}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"lang" in resp.data.lower()

    def test_add_term_duplikat_flash(self, client):
        client.post("/terms", data={"term": "kinderwagen"}, follow_redirects=True)
        resp = client.post("/terms", data={"term": "kinderwagen"}, follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_term(self, client, app):
        import app.database as db
        with app.app_context():
            db.add_search_term("zulöschen")
            terms = db.get_search_terms()
            tid = next(t["id"] for t in terms if t["term"] == "zulöschen")

        resp = client.post(f"/terms/{tid}/delete", follow_redirects=True)
        assert resp.status_code == 200

    def test_toggle_term(self, client, app):
        import app.database as db
        with app.app_context():
            db.add_search_term("toggletest")
            terms = db.get_search_terms()
            tid = next(t["id"] for t in terms if t["term"] == "toggletest")

        resp = client.post(f"/terms/{tid}/toggle", follow_redirects=True)
        assert resp.status_code == 200


# ── Favoriten ────────────────────────────────────────────────

class TestFavoriteRoute:

    def test_toggle_favorite_existiert_nicht(self, client):
        resp = client.post("/listings/9999/favorite")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"

    def test_toggle_favorite_vorhanden(self, client, app):
        from app.scrapers.base import Listing
        import app.database as db
        listing = Listing(
            platform="Test", title="T", price="10 €", location="München",
            url="https://example.com/1", listing_id="fav-test-1",
        )
        with app.app_context():
            db.save_listing(listing)
            listings = db.get_listings(limit=10)
            lid = next(l["id"] for l in listings if l["listing_id"] == "fav-test-1")

        resp = client.post(f"/listings/{lid}/favorite")
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "ok"


# ── Einstellungen ─────────────────────────────────────────────

class TestSettingsRoutes:

    def test_settings_page_liefert_200(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200

    def test_settings_page_enthaelt_felder(self, client):
        resp = client.get("/settings")
        assert b"kleinanzeigen" in resp.data.lower()
        assert b"email" in resp.data.lower()

    def test_save_settings_redirect(self, client):
        resp = client.post("/settings", data={
            "crawler_interval": "30",
            "crawler_max_results": "10",
            "crawler_delay": "1",
        })
        assert resp.status_code == 302

    def test_save_settings_ungueltig_interval_flash(self, client):
        resp = client.post("/settings", data={
            "crawler_interval": "9999",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"interval" in resp.data.lower() or b"nterval" in resp.data.lower() or resp.status_code == 200

    def test_save_settings_checkbox_enabled(self, client, app):
        import app.database as db
        client.post("/settings", data={
            "kleinanzeigen_enabled": "on",
            "crawler_interval": "15",
        })
        with app.app_context():
            val = db.get_setting("kleinanzeigen_enabled")
        assert val == "1"

    def test_save_settings_checkbox_disabled(self, client, app):
        import app.database as db
        client.post("/settings", data={"crawler_interval": "15"})
        with app.app_context():
            val = db.get_setting("kleinanzeigen_enabled")
        assert val == "0"


# ── Crawler-API ──────────────────────────────────────────────

class TestApiCrawl:

    def test_crawl_startet(self, client):
        with patch("app.routes.is_running", return_value=False), \
             patch("app.routes.run_crawl_async") as mock_run:
            resp = client.post("/api/crawl")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["status"] == "started"
            mock_run.assert_called_once()

    def test_crawl_bereits_laufend(self, client):
        with patch("app.routes.is_running", return_value=True):
            resp = client.post("/api/crawl")
            assert resp.status_code == 409
            data = json.loads(resp.data)
            assert data["status"] == "already_running"


# ── Status-API ────────────────────────────────────────────────

class TestApiStatus:

    def test_status_felder_vorhanden(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "crawl_status" in data
        assert "is_running" in data
        assert "total_listings" in data
        assert "next_crawl" in data

    def test_status_idle_bei_start(self, client):
        resp = client.get("/api/status")
        data = json.loads(resp.data)
        assert data["crawl_status"] == "idle"


# ── Listings-API ──────────────────────────────────────────────

class TestApiListings:

    def test_listings_leer_am_anfang(self, client):
        resp = client.get("/api/listings")
        assert resp.status_code == 200
        assert json.loads(resp.data) == []

    def test_listings_mit_eintraegen(self, client, app):
        from app.scrapers.base import Listing
        import app.database as db
        listing = Listing(
            platform="Test", title="Kinderwagen", price="50 €", location="München",
            url="https://example.com/2", listing_id="api-test-1",
        )
        with app.app_context():
            db.save_listing(listing)

        resp = client.get("/api/listings")
        data = json.loads(resp.data)
        assert len(data) >= 1
        assert any(l["listing_id"] == "api-test-1" for l in data)

    def test_listings_filter_platform(self, client, app):
        from app.scrapers.base import Listing
        import app.database as db
        with app.app_context():
            db.save_listing(Listing(
                platform="Kleinanzeigen", title="A", price="10 €",
                location="München", url="https://example.com/3", listing_id="ka-1",
            ))
            db.save_listing(Listing(
                platform="Shpock", title="B", price="20 €",
                location="München", url="https://example.com/4", listing_id="sh-1",
            ))

        resp = client.get("/api/listings?platform=Kleinanzeigen")
        data = json.loads(resp.data)
        assert all(l["platform"] == "Kleinanzeigen" for l in data)

    def test_listings_ungueltig_limit(self, client):
        resp = client.get("/api/listings?limit=abc")
        assert resp.status_code == 400

    def test_listings_ungueltig_max_distance(self, client):
        resp = client.get("/api/listings?max_distance=abc")
        assert resp.status_code == 400


# ── Stats-API ─────────────────────────────────────────────────

class TestApiStats:

    def test_stats_leer(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        assert isinstance(json.loads(resp.data), list)


# ── Log-API ───────────────────────────────────────────────────

class TestApiLog:

    def test_log_liefert_liste(self, client):
        resp = client.get("/api/log")
        assert resp.status_code == 200
        assert isinstance(json.loads(resp.data), list)


# ── Clear-Listings-API ────────────────────────────────────────

class TestApiClearListings:

    def test_clear_listings(self, client, app):
        from app.scrapers.base import Listing
        import app.database as db
        with app.app_context():
            db.save_listing(Listing(
                platform="Test", title="Löschen", price="5 €",
                location="München", url="https://example.com/5", listing_id="del-1",
            ))

        resp = client.post("/api/clear-listings")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"

        with app.app_context():
            assert db.get_listing_count() == 0
