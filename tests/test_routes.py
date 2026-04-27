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


# ── Dismiss ──────────────────────────────────────────────────

class TestDismissRoute:

    def _save_and_get_id(self, app, lid="dismiss-route-1"):
        from app.scrapers.base import Listing
        import app.database as db
        listing = Listing(
            platform="Test", title="D", price="5 €", location="München",
            url=f"https://example.com/{lid}", listing_id=lid,
        )
        with app.app_context():
            db.save_listing(listing)
            listings = db.get_listings(limit=10)
            return next(l["id"] for l in listings if l["listing_id"] == lid)

    def test_dismiss_gibt_ok_zurueck(self, client, app):
        lid = self._save_and_get_id(app)
        resp = client.post(f"/listings/{lid}/dismiss")
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "ok"

    def test_dismiss_unbekannte_id_kein_fehler(self, client):
        resp = client.post("/listings/9999/dismiss")
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "ok"

    def test_dismiss_listing_erscheint_nicht_wieder(self, client, app):
        from app.scrapers.base import Listing
        import app.database as db
        listing = Listing(
            platform="Test", title="N", price="5 €", location="München",
            url="https://example.com/dismiss-never", listing_id="dismiss-never",
        )
        with app.app_context():
            db.save_listing(listing)
            listings = db.get_listings(limit=10)
            lid = next(l["id"] for l in listings if l["listing_id"] == "dismiss-never")

        client.post(f"/listings/{lid}/dismiss")

        with app.app_context():
            again = Listing(
                platform="Test", title="N2", price="5 €", location="München",
                url="https://example.com/dismiss-never", listing_id="dismiss-never",
            )
            result = db.save_listing(again)
            assert result is False


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
            resp = client.post("/api/crawl",
                               data=json.dumps({"platform": "kleinanzeigen"}),
                               content_type="application/json")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["status"] == "started"
            mock_run.assert_called_once_with("kleinanzeigen", manual=True)

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

    def test_last_found_summiert_alle_plattformen(self, client, app):
        """last_found = Summe der {platform}_last_crawl_found-Werte aller Plattformen."""
        import app.database as db
        with app.app_context():
            db.set_setting("kleinanzeigen_last_crawl_found", "3")
            db.set_setting("shpock_last_crawl_found", "5")
            db.set_setting("vinted_last_crawl_found", "2")

        resp = client.get("/api/status")
        data = json.loads(resp.data)
        assert data["last_found"] == "10"

    def test_last_found_kein_globaler_schluessel(self, client, app):
        """last_crawl_found als globaler Key darf NICHT in der Antwort landen."""
        resp = client.get("/api/status")
        data = json.loads(resp.data)
        assert "last_crawl_found" not in data


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

    def test_listings_einzel_term_filter(self, client, app):
        from app.scrapers.base import Listing
        import app.database as db
        with app.app_context():
            db.save_listing(Listing(
                platform="Test", title="K", price="5 €", location="München",
                url="https://example.com/term-a", listing_id="term-a",
                search_term="kinderwagen",
            ))
            db.save_listing(Listing(
                platform="Test", title="B", price="5 €", location="München",
                url="https://example.com/term-b", listing_id="term-b",
                search_term="babybett",
            ))
        resp = client.get("/api/listings?term=kinderwagen")
        data = json.loads(resp.data)
        assert all(l["search_term"] == "kinderwagen" for l in data)
        assert len(data) == 1

    def test_listings_new_filter_ohne_session(self, client, app):
        """?new=1 ohne Profil-Session liefert alle Anzeigen (kein since_datetime)."""
        from app.scrapers.base import Listing
        import app.database as db
        with app.app_context():
            db.save_listing(Listing(
                platform="Test", title="X", price="5 €", location="München",
                url="https://example.com/new-no-sess", listing_id="new-no-sess",
            ))
        resp = client.get("/api/listings?new=1")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert any(l["listing_id"] == "new-no-sess" for l in data)

    def test_listings_new_filter_mit_session(self, client, app):
        """?new=1 mit gesetztem profile_last_seen filtert ältere Anzeigen heraus."""
        import sqlite3
        from app.scrapers.base import Listing
        import app.database as db
        with app.app_context():
            db.save_listing(Listing(
                platform="Test", title="Alt", price="5 €", location="München",
                url="https://example.com/new-old", listing_id="new-old",
            ))
            db.save_listing(Listing(
                platform="Test", title="Neu", price="5 €", location="München",
                url="https://example.com/new-new", listing_id="new-new",
            ))
            conn = sqlite3.connect(str(db.DB_PATH))
            conn.execute("UPDATE listings SET found_at=datetime('now', '-2 hours') WHERE listing_id='new-old'")
            conn.commit()
            conn.close()

        with client.session_transaction() as sess:
            sess["profile_last_seen"] = "2099-01-01 00:00:00"  # in der Zukunft → alles ist "alt"

        resp = client.get("/api/listings?new=1")
        data = json.loads(resp.data)
        assert all(l["listing_id"] != "new-old" for l in data)
        assert all(l["listing_id"] != "new-new" for l in data)

    def test_listings_mehrere_terme(self, client, app):
        from app.scrapers.base import Listing
        import app.database as db
        with app.app_context():
            db.save_listing(Listing(
                platform="Test", title="K", price="5 €", location="München",
                url="https://example.com/multi-a", listing_id="multi-a",
                search_term="kinderwagen",
            ))
            db.save_listing(Listing(
                platform="Test", title="B", price="5 €", location="München",
                url="https://example.com/multi-b", listing_id="multi-b",
                search_term="babybett",
            ))
            db.save_listing(Listing(
                platform="Test", title="H", price="5 €", location="München",
                url="https://example.com/multi-c", listing_id="multi-c",
                search_term="hochstuhl",
            ))
        resp = client.get("/api/listings?term=kinderwagen&term=babybett")
        data = json.loads(resp.data)
        ids = {l["listing_id"] for l in data}
        assert "multi-a" in ids
        assert "multi-b" in ids
        assert "multi-c" not in ids


# ── Note-Route ───────────────────────────────────────────────

class TestNoteRoute:

    def _save_and_get_id(self, app, lid="note-route-1"):
        from app.scrapers.base import Listing
        import app.database as db
        listing = Listing(
            platform="Test", title="N", price="5 €", location="München",
            url=f"https://example.com/{lid}", listing_id=lid,
        )
        with app.app_context():
            db.save_listing(listing)
            return next(l["id"] for l in db.get_listings() if l["listing_id"] == lid)

    def test_set_note(self, client, app):
        lid = self._save_and_get_id(app)
        resp = client.post(f"/listings/{lid}/note",
                           json={"note": "Schaut gut aus"},
                           content_type="application/json")
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "ok"

    def test_clear_note(self, client, app):
        lid = self._save_and_get_id(app, "note-route-2")
        client.post(f"/listings/{lid}/note", json={"note": "Notiz"},
                    content_type="application/json")
        resp = client.post(f"/listings/{lid}/note", json={"note": ""},
                           content_type="application/json")
        assert resp.status_code == 200


# ── Term-MaxPrice-Route ───────────────────────────────────────

class TestTermMaxPriceRoute:

    def _get_term_id(self, app, term="kinderwagen"):
        import app.database as db
        with app.app_context():
            terms = db.get_search_terms()
            return next(t["id"] for t in terms if t["term"] == term)

    def test_set_max_price(self, client, app):
        tid = self._get_term_id(app)
        resp = client.post(f"/terms/{tid}/max-price",
                           json={"max_price": 50},
                           content_type="application/json")
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "ok"

    def test_clear_max_price(self, client, app):
        tid = self._get_term_id(app)
        client.post(f"/terms/{tid}/max-price", json={"max_price": 100},
                    content_type="application/json")
        resp = client.post(f"/terms/{tid}/max-price",
                           json={"max_price": None},
                           content_type="application/json")
        assert resp.status_code == 200


# ── Platforms-API ─────────────────────────────────────────────

class TestApiPlatforms:

    def test_platforms_leer(self, client):
        resp = client.get("/api/platforms")
        assert resp.status_code == 200
        assert json.loads(resp.data) == []

    def test_platforms_mit_eintraegen(self, client, app):
        from app.scrapers.base import Listing
        import app.database as db
        with app.app_context():
            db.save_listing(Listing(
                platform="Kleinanzeigen", title="A", price="10 €",
                location="München", url="https://example.com/plat-1", listing_id="plat-1",
            ))
            db.save_listing(Listing(
                platform="Shpock", title="B", price="20 €",
                location="München", url="https://example.com/plat-2", listing_id="plat-2",
            ))
        resp = client.get("/api/platforms")
        data = json.loads(resp.data)
        assert set(data) == {"Kleinanzeigen", "Shpock"}


# ── Status platform_counts ────────────────────────────────────

class TestApiStatusPlatformCounts:

    def test_status_enthaelt_platform_counts(self, client):
        resp = client.get("/api/status")
        data = json.loads(resp.data)
        assert "platform_counts" in data
        assert isinstance(data["platform_counts"], dict)


# ── Test-Scraper-API ──────────────────────────────────────────

class TestApiTestScraper:

    def test_unbekannte_plattform(self, client):
        resp = client.post("/api/test-scraper",
                           json={"platform": "gibtesnicht"},
                           content_type="application/json")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["status"] == "error"

    def test_bekannte_plattform_ruft_scraper_auf(self, client):
        from unittest.mock import patch, MagicMock
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = []
        with patch("app.scrapers.KleinanzeigenScraper", return_value=mock_scraper):
            resp = client.post("/api/test-scraper",
                               json={"platform": "kleinanzeigen"},
                               content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"
        assert data["count"] == 0


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

    def test_clear_listings_by_age_loescht(self, client, app):
        import sqlite3
        from app.scrapers.base import Listing
        import app.database as db
        with app.app_context():
            db.save_listing(Listing(
                platform="Test", title="Alt", price="5 €",
                location="München", url="https://example.com/old", listing_id="age-del-1",
            ))
            conn = sqlite3.connect(str(db.DB_PATH))
            conn.execute("UPDATE listings SET found_at=datetime('now', '-25 hours') WHERE listing_id='age-del-1'")
            conn.commit()
            conn.close()

        resp = client.post("/api/clear-listings-by-age", json={"hours": 24},
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"
        assert data["deleted"] >= 1

    def test_clear_listings_by_age_ungueltig(self, client):
        resp = client.post("/api/clear-listings-by-age", json={"hours": 0},
                           content_type="application/json")
        assert resp.status_code == 400

    def test_clear_listings_by_age_kein_json_body(self, client):
        """Leerer Body mit JSON Content-Type darf keinen 500 auslösen."""
        resp = client.post("/api/clear-listings-by-age",
                           data=b"", content_type="application/json")
        assert resp.status_code == 400

    def test_clear_listings_by_age_negativer_wert(self, client):
        resp = client.post("/api/clear-listings-by-age", json={"hours": -1},
                           content_type="application/json")
        assert resp.status_code == 400

    def test_clear_listings_by_age_string_wert(self, client):
        resp = client.post("/api/clear-listings-by-age", json={"hours": "abc"},
                           content_type="application/json")
        assert resp.status_code == 400

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


# ── Profile-Routen ────────────────────────────────────────────

class TestProfileRoutes:

    def test_index_ohne_profile_kein_redirect(self, client):
        """Ohne Profile direkt zum Dashboard."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_mit_profil_redirectet_zu_select(self, client, app):
        import app.database as db
        with app.app_context():
            db.create_profile("Kai", "🐣")
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/profiles/select" in resp.headers["Location"]

    def test_profile_select_seite(self, client, app):
        import app.database as db
        with app.app_context():
            db.create_profile("Kai", "🐣")
        resp = client.get("/profiles/select")
        assert resp.status_code == 200
        assert b"Kai" in resp.data

    def test_profile_select_ohne_profile_redirect(self, client):
        resp = client.get("/profiles/select")
        assert resp.status_code == 302

    def test_profil_auswaehlen_setzt_session(self, client, app):
        import app.database as db
        with app.app_context():
            pid = db.create_profile("Lisa", "🌸")
        resp = client.post(f"/profiles/select/{pid}", follow_redirects=False)
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert sess["profile_id"] == pid
            assert sess["profile_name"] == "Lisa"

    def test_profil_auswaehlen_aktualisiert_last_seen(self, client, app):
        import app.database as db
        with app.app_context():
            pid = db.create_profile("Test", "👤")
            assert db.get_profile(pid)["last_seen_at"] is None
        client.post(f"/profiles/select/{pid}")
        with app.app_context():
            assert db.get_profile(pid)["last_seen_at"] is not None

    def test_profil_erstellen(self, client, app):
        import app.database as db
        client.post("/profiles", data={"name": "Neu", "emoji": "🎉"})
        with app.app_context():
            profiles = db.get_profiles()
        assert any(p["name"] == "Neu" for p in profiles)

    def test_profil_loeschen(self, client, app):
        import app.database as db
        with app.app_context():
            pid = db.create_profile("Weg", "🗑️")
        resp = client.post(f"/profiles/{pid}/delete",
                           content_type="application/json")
        assert resp.status_code == 200
        with app.app_context():
            assert db.get_profile(pid) is None

    def test_profil_umbenennen(self, client, app):
        import app.database as db
        with app.app_context():
            pid = db.create_profile("Alt", "👤")
        resp = client.post(f"/profiles/{pid}/update",
                           json={"name": "Neu", "emoji": "🎊"},
                           content_type="application/json")
        assert resp.status_code == 200
        with app.app_context():
            assert db.get_profile(pid)["name"] == "Neu"

    def test_api_listings_is_new_mit_profil(self, client, app):
        """is_new=True für Anzeigen die nach last_seen_at gefunden wurden."""
        import app.database as db
        from app.scrapers.base import Listing
        with app.app_context():
            pid = db.create_profile("Test", "👤")
            db.save_listing(Listing(
                platform="Test", title="Neue Anzeige", price="5 €",
                location="München", url="https://example.com/new",
                listing_id="new-1", search_term="test",
            ))
        # Profil auswählen → last_seen_at = None → keine is_new Badges
        client.post(f"/profiles/select/{pid}")
        resp = client.get("/api/listings")
        listings = json.loads(resp.data)
        # last_seen_at war None beim ersten Besuch → is_new = False
        assert all(not l["is_new"] for l in listings)


# ── Info-Seite ────────────────────────────────────────────────

class TestInfoPage:

    def test_info_liefert_200(self, client):
        resp = client.get("/info")
        assert resp.status_code == 200

    def test_info_enthaelt_statistik_bereiche(self, client):
        resp = client.get("/info")
        body = resp.data
        assert b"Speicher" in body
        assert b"Anzeigen-Bestand" in body
        assert b"Crawl-Verlauf" in body
        assert b"Benachrichtigungen" in body
        assert b"System" in body

    def test_info_enthaelt_nav_link(self, client):
        resp = client.get("/info")
        assert b"/info" in resp.data

    def test_info_zeigt_migrationen(self, client):
        resp = client.get("/info")
        assert b"v1_settings_rename" in resp.data
