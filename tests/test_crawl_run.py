"""Tests für app/crawler.py: run_crawl() Orchestrierung."""

import pytest
from unittest.mock import patch, MagicMock, call
from app.scrapers.base import Listing
import app.crawler as crawler_module


def make_listing(**kwargs) -> Listing:
    defaults = dict(
        platform="Test", title="Kinderwagen", price="50 €",
        location="München", url="https://example.com/1",
        listing_id="test-1", search_term="kinderwagen", description="",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


@pytest.fixture()
def patched_db(tmp_path, monkeypatch):
    """Frische DB + monkeypatcht DB_PATH im database-Modul."""
    import app.database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db


# ── Basis-Orchestrierung ─────────────────────────────────────

class TestRunCrawlOrchestration:

    def test_kein_suchbegriff_gibt_no_terms_zurueck(self, patched_db):
        patched_db.init_db()
        # Alle Default-Suchbegriffe deaktivieren/löschen
        for t in patched_db.get_search_terms():
            patched_db.delete_search_term(t["id"])

        result = crawler_module.run_crawl()
        assert result["status"] == "no_terms"

    def test_keine_plattform_gibt_no_platforms_zurueck(self, patched_db):
        patched_db.set_setting("kleinanzeigen_enabled", "0")
        patched_db.set_setting("shpock_enabled", "0")
        patched_db.set_setting("facebook_enabled", "0")
        patched_db.set_setting("vinted_enabled", "0")
        patched_db.set_setting("ebay_enabled", "0")

        result = crawler_module.run_crawl()
        assert result["status"] == "no_platforms"

    def test_crawl_setzt_status_auf_running_dann_idle(self, patched_db):
        statuses = []

        original_set_setting = patched_db.set_setting
        def tracking_set_setting(key, value):
            if key == "crawl_status":
                statuses.append(value)
            original_set_setting(key, value)

        mock_scraper = MagicMock()
        mock_scraper.search.return_value = []

        with patch.object(patched_db, "set_setting", side_effect=tracking_set_setting), \
             patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=False), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting", side_effect=tracking_set_setting):
            crawler_module.run_crawl()

        assert "running" in statuses
        assert statuses[-1] == "idle"

    def test_neue_listings_werden_gespeichert(self, patched_db):
        listing = make_listing(listing_id="new-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True) as mock_save, \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl()

        assert result["new"] == 1
        mock_save.assert_called_once()

    def test_blacklist_filtert_listings_heraus(self, patched_db):
        listing = make_listing(title="defekter Kinderwagen", listing_id="bl-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "defekt",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True) as mock_save, \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl()

        assert result["new"] == 0
        assert result["skipped_blacklist"] == 1
        mock_save.assert_not_called()

    def test_gratis_listings_werden_gezaehlt(self, patched_db):
        listing = make_listing(listing_id="free-1", price="0 €")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl()

        assert result["free"] >= 1

    def test_scraper_fehler_inkrementiert_errors(self, patched_db):
        mock_scraper = MagicMock()
        mock_scraper.search.side_effect = RuntimeError("API kaputt")

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=False), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl()

        assert result["errors"] >= 1
        assert result["status"] == "ok"

    def test_notify_wird_nur_bei_neuen_listings_aufgerufen(self, patched_db):
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = []

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=False), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify") as mock_notify:
            crawler_module.run_crawl()

        mock_notify.assert_not_called()

    def test_notify_wird_bei_neuen_listings_aufgerufen(self, patched_db):
        listing = make_listing(listing_id="notify-1")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.db.update_listing_distance"), \
             patch("app.crawler.notify") as mock_notify:
            crawler_module.run_crawl()

        mock_notify.assert_called_once()

    def test_entfernung_wird_berechnet_wenn_location_vorhanden(self, patched_db):
        listing = make_listing(listing_id="dist-1", location="Augsburg")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.distance_to_home", return_value=55.3) as mock_dist, \
             patch("app.crawler.db.update_listing_distance") as mock_update, \
             patch("app.crawler.notify"):
            crawler_module.run_crawl()

        mock_dist.assert_called_once()
        mock_update.assert_called_once()

    def test_entfernung_fehler_bricht_crawl_nicht_ab(self, patched_db):
        listing = make_listing(listing_id="dist-err-1", location="Unbekannt")
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = [listing]

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=True), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.distance_to_home", side_effect=RuntimeError("Geo kaputt")), \
             patch("app.crawler.notify"):
            result = crawler_module.run_crawl()

        assert result["new"] == 1


# ── Double-Run-Schutz ─────────────────────────────────────────

class TestRunCrawlLock:

    def test_is_running_false_initial(self):
        assert crawler_module.is_running() is False

    def test_run_crawl_async_gibt_thread_zurueck(self, patched_db):
        import threading
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = []

        with patch("app.crawler.KleinanzeigenScraper", return_value=mock_scraper), \
             patch("app.crawler.db.get_settings", return_value={
                 "kleinanzeigen_enabled": "1",
                 "shpock_enabled": "0", "facebook_enabled": "0",
                 "vinted_enabled": "0", "ebay_enabled": "0",
                 "crawler_delay": "0", "crawler_max_results": "5",
                 "crawler_blacklist": "",
             }), \
             patch("app.crawler.db.get_search_terms", return_value=[{"term": "kinderwagen"}]), \
             patch("app.crawler.db.save_listing", return_value=False), \
             patch("app.crawler.db.clear_old_listings"), \
             patch("app.crawler.db.set_setting"), \
             patch("app.crawler.notify"):
            t = crawler_module.run_crawl_async()
            assert isinstance(t, threading.Thread)
            t.join(timeout=5)
