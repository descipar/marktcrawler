"""Tests für app/database.py: CRUD-Operationen mit temporärer SQLite-DB."""

import pytest
from app.scrapers.base import Listing


# ── Fixtures ─────────────────────────────────────────────────
# temp_db kommt aus conftest.py und liefert ein frisches db-Modul


# ── Search Terms ─────────────────────────────────────────────

class TestSearchTerms:

    def test_default_terms_wurden_angelegt(self, temp_db):
        """Nach init_db() müssen die Default-Suchbegriffe vorhanden sein."""
        terms = temp_db.get_search_terms()
        names = [t["term"] for t in terms]
        assert "kinderwagen" in names
        assert "babybett" in names

    def test_neuen_term_hinzufuegen(self, temp_db):
        before = len(temp_db.get_search_terms())
        ok = temp_db.add_search_term("testbegriff")
        assert ok is True
        assert len(temp_db.get_search_terms()) == before + 1

    def test_duplikat_wird_abgelehnt(self, temp_db):
        temp_db.add_search_term("duplikat")
        ok = temp_db.add_search_term("duplikat")
        assert ok is False

    def test_term_loeschen(self, temp_db):
        temp_db.add_search_term("zulöschen")
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "zulöschen")
        temp_db.delete_search_term(tid)
        names = [t["term"] for t in temp_db.get_search_terms()]
        assert "zulöschen" not in names

    def test_term_aktivieren_deaktivieren(self, temp_db):
        temp_db.add_search_term("toggletest")
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "toggletest")

        # Initial: enabled
        temp_db.toggle_search_term(tid)
        terms = temp_db.get_search_terms()
        t = next(t for t in terms if t["id"] == tid)
        assert t["enabled"] == 0

        # Wieder aktivieren
        temp_db.toggle_search_term(tid)
        terms = temp_db.get_search_terms()
        t = next(t for t in terms if t["id"] == tid)
        assert t["enabled"] == 1

    def test_enabled_only_filter(self, temp_db):
        temp_db.add_search_term("aktiv")
        temp_db.add_search_term("inaktiv")
        terms = temp_db.get_search_terms()
        inaktiv_id = next(t["id"] for t in terms if t["term"] == "inaktiv")
        temp_db.toggle_search_term(inaktiv_id)

        aktive = temp_db.get_search_terms(enabled_only=True)
        names = [t["term"] for t in aktive]
        assert "aktiv" in names
        assert "inaktiv" not in names


# ── Settings ─────────────────────────────────────────────────

class TestSettings:

    def test_defaults_wurden_geladen(self, temp_db):
        s = temp_db.get_settings()
        assert "crawler_interval" in s
        assert s["crawler_interval"] == "15"

    def test_setting_speichern_und_lesen(self, temp_db):
        temp_db.set_setting("test_key", "test_value")
        assert temp_db.get_setting("test_key") == "test_value"

    def test_setting_ueberschreiben(self, temp_db):
        temp_db.set_setting("crawler_interval", "30")
        assert temp_db.get_setting("crawler_interval") == "30"

    def test_unbekanntes_setting_liefert_default(self, temp_db):
        val = temp_db.get_setting("gibt_es_nicht", default="fallback")
        assert val == "fallback"

    def test_save_settings_batch(self, temp_db):
        temp_db.save_settings({"crawler_interval": "15", "crawler_delay": "1"})
        assert temp_db.get_setting("crawler_interval") == "15"
        assert temp_db.get_setting("crawler_delay") == "1"


# ── Listings ─────────────────────────────────────────────────

def make_listing(listing_id="test-001", title="Kinderwagen", is_free=False) -> Listing:
    return Listing(
        platform="Kleinanzeigen",
        title=title,
        price="50 €",
        location="Dortmund",
        url=f"https://example.com/{listing_id}",
        listing_id=listing_id,
        search_term="kinderwagen",
        is_free=is_free,
    )


class TestListings:

    def test_neue_anzeige_speichern(self, temp_db):
        ok = temp_db.save_listing(make_listing("neu-001"))
        assert ok is True
        assert temp_db.get_listing_count() == 1

    def test_duplikat_wird_ignoriert(self, temp_db):
        temp_db.save_listing(make_listing("dup-001"))
        ok = temp_db.save_listing(make_listing("dup-001"))
        assert ok is False
        assert temp_db.get_listing_count() == 1

    def test_mehrere_anzeigen(self, temp_db):
        for i in range(5):
            temp_db.save_listing(make_listing(f"multi-{i:03d}"))
        assert temp_db.get_listing_count() == 5

    def test_get_listings_limit(self, temp_db):
        for i in range(10):
            temp_db.save_listing(make_listing(f"limit-{i:03d}"))
        result = temp_db.get_listings(limit=3)
        assert len(result) == 3

    def test_get_listings_nur_gratis(self, temp_db):
        temp_db.save_listing(make_listing("gratis-001", is_free=True))
        temp_db.save_listing(make_listing("normal-001", is_free=False))
        result = temp_db.get_listings(only_free=True)
        assert len(result) == 1
        assert result[0]["listing_id"] == "gratis-001"

    def test_is_free_wird_gespeichert(self, temp_db):
        temp_db.save_listing(make_listing("frei-001", is_free=True))
        listings = temp_db.get_listings()
        assert listings[0]["is_free"] == 1

    def test_entfernung_aktualisieren(self, temp_db):
        temp_db.save_listing(make_listing("dist-001"))
        temp_db.update_listing_distance("dist-001", 42.3)
        listings = temp_db.get_listings()
        assert listings[0]["distance_km"] == pytest.approx(42.3, abs=0.05)

    def test_toggle_favorit(self, temp_db):
        temp_db.save_listing(make_listing("fav-001"))
        listing = temp_db.get_listings()[0]
        lid = listing["id"]
        assert listing["is_favorite"] == 0

        temp_db.toggle_favorite(lid)
        assert temp_db.get_listings()[0]["is_favorite"] == 1

        temp_db.toggle_favorite(lid)
        assert temp_db.get_listings()[0]["is_favorite"] == 0

    def test_favoriten_filter(self, temp_db):
        temp_db.save_listing(make_listing("fav-a"))
        temp_db.save_listing(make_listing("fav-b"))
        lid = temp_db.get_listings()[0]["id"]
        temp_db.toggle_favorite(lid)

        result = temp_db.get_listings(only_favorites=True)
        assert len(result) == 1

    def test_favoriten_bleiben_bei_clear_old_listings(self, temp_db):
        """Favoriten dürfen beim automatischen Aufräumen nicht gelöscht werden."""
        import sqlite3

        temp_db.save_listing(make_listing("old-fav"))
        temp_db.save_listing(make_listing("old-normal"))

        # Beide Anzeigen künstlich alt machen (31 Tage)
        conn = sqlite3.connect(str(temp_db.DB_PATH))
        conn.execute("UPDATE listings SET found_at = datetime('now', '-31 days')")
        conn.commit()
        conn.close()

        # Favorit setzen
        fav_id = next(l["id"] for l in temp_db.get_listings() if l["listing_id"] == "old-fav")
        temp_db.toggle_favorite(fav_id)

        temp_db.clear_old_listings(days=30)

        remaining = [l["listing_id"] for l in temp_db.get_listings()]
        assert "old-fav" in remaining
        assert "old-normal" not in remaining

    def test_offset_paginierung(self, temp_db):
        for i in range(5):
            temp_db.save_listing(make_listing(f"page-{i:03d}"))
        page1 = temp_db.get_listings(limit=3, offset=0)
        page2 = temp_db.get_listings(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2
        ids1 = {l["listing_id"] for l in page1}
        ids2 = {l["listing_id"] for l in page2}
        assert ids1.isdisjoint(ids2)


class TestSortierung:

    def _save_listings(self, temp_db):
        """Legt drei Listings mit unterschiedlichen Preisen und Distanzen an."""
        from app.scrapers.base import Listing
        entries = [
            ("sort-a", "10 €", 5.0),
            ("sort-b", "50 €", 30.0),
            ("sort-c", "25 €", 15.0),
        ]
        for lid, price, dist in entries:
            l = Listing(
                platform="Test", title=lid, price=price,
                location="München", url=f"https://example.com/{lid}",
                listing_id=lid, search_term="test",
            )
            temp_db.save_listing(l)
            temp_db.update_listing_distance(lid, dist)

    def test_sort_preis_aufsteigend(self, temp_db):
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="price_asc")
        prices = [l["price"] for l in result]
        assert prices == ["10 €", "25 €", "50 €"]

    def test_sort_preis_absteigend(self, temp_db):
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="price_desc")
        prices = [l["price"] for l in result]
        assert prices == ["50 €", "25 €", "10 €"]

    def test_sort_entfernung_aufsteigend(self, temp_db):
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="distance_asc")
        ids = [l["listing_id"] for l in result]
        assert ids == ["sort-a", "sort-c", "sort-b"]

    def test_sort_entfernung_null_ans_ende(self, temp_db):
        """Listings ohne Distanz landen beim Entfernungs-Sort am Ende."""
        from app.scrapers.base import Listing
        l_ohne = Listing(
            platform="Test", title="ohne", price="5 €",
            location="", url="https://example.com/ohne",
            listing_id="ohne-dist", search_term="test",
        )
        temp_db.save_listing(l_ohne)
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="distance_asc")
        assert result[-1]["listing_id"] == "ohne-dist"

    def test_sort_preis_ohne_preis_ans_ende(self, temp_db):
        """Listings mit nicht-numerischem Preis landen beim Preis-Sort am Ende."""
        from app.scrapers.base import Listing
        l_ka = Listing(
            platform="Test", title="ka", price="k.A.",
            location="München", url="https://example.com/ka",
            listing_id="preis-ka", search_term="test",
        )
        temp_db.save_listing(l_ka)
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="price_asc")
        assert result[-1]["listing_id"] == "preis-ka"

    def test_sort_unbekannter_wert_faellt_auf_default(self, temp_db):
        """Ungültiger sort_by-Wert löst keinen Fehler aus."""
        self._save_listings(temp_db)
        result = temp_db.get_listings(sort_by="gibts_nicht")
        assert len(result) == 3

    def test_favoriten_bleiben_immer_oben(self, temp_db):
        """Favoriten erscheinen unabhängig von der Sortierung zuerst."""
        self._save_listings(temp_db)
        fav_id = next(l["id"] for l in temp_db.get_listings() if l["listing_id"] == "sort-b")
        temp_db.toggle_favorite(fav_id)
        result = temp_db.get_listings(sort_by="price_asc")
        assert result[0]["listing_id"] == "sort-b"


# ── Geocache ─────────────────────────────────────────────────

class TestGeocache:

    def test_speichern_und_laden(self, temp_db):
        temp_db.save_geocache("Dortmund", 51.5136, 7.4653)
        result = temp_db.get_geocache("Dortmund")
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(51.5136)
        assert lon == pytest.approx(7.4653)

    def test_unbekannter_ort_gibt_none(self, temp_db):
        assert temp_db.get_geocache("NichtVorhanden") is None

    def test_ueberschreiben_funktioniert(self, temp_db):
        temp_db.save_geocache("Ort", 10.0, 20.0)
        temp_db.save_geocache("Ort", 11.0, 21.0)
        lat, lon = temp_db.get_geocache("Ort")
        assert lat == pytest.approx(11.0)


# ── Migration ─────────────────────────────────────────────────

class TestMigration:

    def test_migration_fuegt_fehlende_spalten_hinzu(self, tmp_path, monkeypatch):
        """
        Simuliert eine alte DB ohne is_favorite/is_free/distance_km
        und prüft, dass _migrate_listings() die Spalten ergänzt.
        """
        import sqlite3
        import app.database as db

        old_db = tmp_path / "old.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)

        # Alte DB ohne neue Spalten anlegen
        conn = sqlite3.connect(str(old_db))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS listings (
                id         INTEGER PRIMARY KEY,
                listing_id TEXT UNIQUE,
                platform   TEXT,
                title      TEXT,
                price      TEXT,
                location   TEXT,
                url        TEXT,
                found_at   TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS geocache (
                location_text TEXT PRIMARY KEY, lat REAL, lon REAL
            );
        """)
        conn.commit()
        conn.close()

        # Migration ausführen
        db.init_db()

        # Prüfen ob neue Spalten vorhanden
        conn = sqlite3.connect(str(old_db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
        conn.close()

        assert "is_favorite" in cols
        assert "is_free" in cols
        assert "distance_km" in cols
