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


class TestSearchTermsFilter:

    def _save(self, temp_db, lid, term):
        from app.scrapers.base import Listing
        temp_db.save_listing(Listing(
            platform="Test", title=lid, price="10 €", location="München",
            url=f"https://example.com/{lid}", listing_id=lid, search_term=term,
        ))

    def test_einzel_term_filter(self, temp_db):
        self._save(temp_db, "a", "kinderwagen")
        self._save(temp_db, "b", "babybett")
        result = temp_db.get_listings(search_terms=["kinderwagen"])
        assert len(result) == 1
        assert result[0]["listing_id"] == "a"

    def test_mehrere_terme_filter(self, temp_db):
        self._save(temp_db, "c", "kinderwagen")
        self._save(temp_db, "d", "babybett")
        self._save(temp_db, "e", "hochstuhl")
        result = temp_db.get_listings(search_terms=["kinderwagen", "babybett"])
        ids = {l["listing_id"] for l in result}
        assert ids == {"c", "d"}
        assert "e" not in ids

    def test_kein_filter_gibt_alles_zurueck(self, temp_db):
        self._save(temp_db, "f", "kinderwagen")
        self._save(temp_db, "g", "babybett")
        result = temp_db.get_listings(search_terms=None)
        assert len(result) == 2

    def test_unbekannter_term_gibt_leer_zurueck(self, temp_db):
        self._save(temp_db, "h", "kinderwagen")
        result = temp_db.get_listings(search_terms=["gibtesnicht"])
        assert result == []


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


# ── Dismiss ──────────────────────────────────────────────────

class TestDismiss:

    def _save(self, temp_db, lid, term="test"):
        from app.scrapers.base import Listing
        l = Listing(
            platform="Test", title=lid, price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term=term,
        )
        temp_db.save_listing(l)
        return next(l["id"] for l in temp_db.get_listings() if l["listing_id"] == lid)

    def test_dismiss_entfernt_listing(self, temp_db):
        db_id = self._save(temp_db, "dismiss-1")
        temp_db.dismiss_listing(db_id)
        ids = [l["listing_id"] for l in temp_db.get_listings()]
        assert "dismiss-1" not in ids

    def test_dismiss_merkt_listing_id(self, temp_db):
        db_id = self._save(temp_db, "dismiss-2")
        temp_db.dismiss_listing(db_id)
        assert temp_db.is_dismissed("dismiss-2") is True

    def test_undismissed_ist_nicht_geblockt(self, temp_db):
        assert temp_db.is_dismissed("nicht-vorhanden") is False

    def test_save_dismissed_listing_wird_abgelehnt(self, temp_db):
        from app.scrapers.base import Listing
        db_id = self._save(temp_db, "dismiss-3")
        temp_db.dismiss_listing(db_id)
        l = Listing(
            platform="Test", title="wieder", price="5 €",
            location="München", url="https://example.com/dismiss-3",
            listing_id="dismiss-3", search_term="test",
        )
        result = temp_db.save_listing(l)
        assert result is False
        ids = [x["listing_id"] for x in temp_db.get_listings()]
        assert "dismiss-3" not in ids

    def test_dismiss_unbekannte_id_kein_fehler(self, temp_db):
        temp_db.dismiss_listing(9999)


class TestDeleteTermWithListings:

    def test_loeschen_entfernt_zugehoerige_anzeigen(self, temp_db):
        from app.scrapers.base import Listing
        temp_db.add_search_term("wegtest")
        l = Listing(
            platform="Test", title="X", price="5 €",
            location="München", url="https://example.com/x",
            listing_id="weg-1", search_term="wegtest",
        )
        temp_db.save_listing(l)
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "wegtest")
        temp_db.delete_search_term(tid)
        ids = [x["listing_id"] for x in temp_db.get_listings()]
        assert "weg-1" not in ids

    def test_loeschen_belaesst_andere_anzeigen(self, temp_db):
        from app.scrapers.base import Listing
        temp_db.add_search_term("behalten")
        l = Listing(
            platform="Test", title="Y", price="5 €",
            location="München", url="https://example.com/y",
            listing_id="keep-1", search_term="behalten",
        )
        temp_db.save_listing(l)
        terms = temp_db.get_search_terms()
        # Löschen eines anderen Terms
        other_tid = next(t["id"] for t in terms if t["term"] == "kinderwagen")
        temp_db.delete_search_term(other_tid)
        ids = [x["listing_id"] for x in temp_db.get_listings()]
        assert "keep-1" in ids


# ── ExcludeFilter ─────────────────────────────────────────────

class TestExcludeFilter:

    def _make(self, temp_db, lid, title, description=""):
        from app.scrapers.base import Listing
        l = Listing(
            platform="Test", title=title, price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test", description=description,
        )
        temp_db.save_listing(l)

    def test_exclude_filtert_aus_titel(self, temp_db):
        self._make(temp_db, "a", "Schöner Kinderwagen")
        self._make(temp_db, "b", "Kinderwagen defekt")
        result = temp_db.get_listings(exclude_text="defekt")
        ids = [l["listing_id"] for l in result]
        assert "a" in ids
        assert "b" not in ids

    def test_exclude_filtert_aus_beschreibung(self, temp_db):
        self._make(temp_db, "c", "Hochstuhl", description="Leider defekt")
        self._make(temp_db, "d", "Hochstuhl NEU", description="Neuwertig")
        result = temp_db.get_listings(exclude_text="defekt")
        ids = [l["listing_id"] for l in result]
        assert "d" in ids
        assert "c" not in ids

    def test_exclude_none_gibt_alle_zurueck(self, temp_db):
        self._make(temp_db, "e", "Babybett")
        self._make(temp_db, "f", "Babybett defekt")
        result = temp_db.get_listings(exclude_text=None)
        ids = [l["listing_id"] for l in result]
        assert "e" in ids
        assert "f" in ids

    def test_exclude_leerstring_gibt_alle_zurueck(self, temp_db):
        self._make(temp_db, "g", "Laufstall")
        result = temp_db.get_listings(exclude_text="")
        ids = [l["listing_id"] for l in result]
        assert "g" in ids


class TestNotesAndDuplicates:

    def _save(self, temp_db, lid, title="Kinderwagen", platform="Kleinanzeigen"):
        from app.scrapers.base import Listing
        l = Listing(
            platform=platform, title=title, price="30 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test",
        )
        temp_db.save_listing(l)
        return next(x["id"] for x in temp_db.get_listings() if x["listing_id"] == lid)

    def test_update_listing_note_speichert(self, temp_db):
        db_id = self._save(temp_db, "note-1")
        temp_db.update_listing_note(db_id, "Schaut gut aus!")
        l = next(x for x in temp_db.get_listings() if x["listing_id"] == "note-1")
        assert l["notes"] == "Schaut gut aus!"

    def test_update_listing_note_loescht(self, temp_db):
        db_id = self._save(temp_db, "note-2")
        temp_db.update_listing_note(db_id, "Notiz")
        temp_db.update_listing_note(db_id, "")
        l = next(x for x in temp_db.get_listings() if x["listing_id"] == "note-2")
        assert l["notes"] is None

    def test_find_duplicate_platform_findet_anderen_plattform(self, temp_db):
        self._save(temp_db, "dup-ka", title="Kinderwagen Bugaboo Fox 3", platform="Kleinanzeigen")
        result = temp_db.find_duplicate_platform("Kinderwagen Bugaboo Fox 3", "Shpock")
        assert result == "Kleinanzeigen"

    def test_find_duplicate_gleiche_plattform_ignoriert(self, temp_db):
        self._save(temp_db, "dup-same", title="Kinderwagen Bugaboo Fox 3", platform="Kleinanzeigen")
        result = temp_db.find_duplicate_platform("Kinderwagen Bugaboo Fox 3", "Kleinanzeigen")
        assert result is None

    def test_find_duplicate_zu_kurzer_titel(self, temp_db):
        self._save(temp_db, "dup-short", title="ABC", platform="Kleinanzeigen")
        result = temp_db.find_duplicate_platform("ABC", "Shpock")
        assert result is None

    def test_find_duplicate_kein_treffer(self, temp_db):
        result = temp_db.find_duplicate_platform("Ganz einzigartiger Titel XY", "Kleinanzeigen")
        assert result is None


class TestPlatformCounts:

    def _save(self, temp_db, lid, platform):
        from app.scrapers.base import Listing
        temp_db.save_listing(Listing(
            platform=platform, title=lid, price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test",
        ))

    def test_get_distinct_platforms(self, temp_db):
        self._save(temp_db, "p1", "Kleinanzeigen")
        self._save(temp_db, "p2", "Shpock")
        self._save(temp_db, "p3", "Kleinanzeigen")
        platforms = temp_db.get_distinct_platforms()
        assert set(platforms) == {"Kleinanzeigen", "Shpock"}

    def test_get_distinct_platforms_leer(self, temp_db):
        assert temp_db.get_distinct_platforms() == []

    def test_get_platform_counts(self, temp_db):
        self._save(temp_db, "c1", "Kleinanzeigen")
        self._save(temp_db, "c2", "Kleinanzeigen")
        self._save(temp_db, "c3", "Shpock")
        counts = temp_db.get_platform_counts()
        assert counts["Kleinanzeigen"] == 2
        assert counts["Shpock"] == 1

    def test_get_platform_counts_leer(self, temp_db):
        assert temp_db.get_platform_counts() == {}


class TestTermMaxPrice:

    def test_update_term_max_price_setzen(self, temp_db):
        temp_db.add_search_term("pricetest")
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "pricetest")
        temp_db.update_term_max_price(tid, 50)
        terms = temp_db.get_search_terms()
        t = next(t for t in terms if t["term"] == "pricetest")
        assert t["max_price"] == 50

    def test_update_term_max_price_auf_none(self, temp_db):
        temp_db.add_search_term("pricenone")
        terms = temp_db.get_search_terms()
        tid = next(t["id"] for t in terms if t["term"] == "pricenone")
        temp_db.update_term_max_price(tid, 100)
        temp_db.update_term_max_price(tid, None)
        terms = temp_db.get_search_terms()
        t = next(t for t in terms if t["term"] == "pricenone")
        assert t["max_price"] is None


class TestClearListingsOlderThan:

    def _save_old(self, temp_db, lid, hours=25):
        import sqlite3
        from app.scrapers.base import Listing
        temp_db.save_listing(Listing(
            platform="Test", title=lid, price="10 €",
            location="München", url=f"https://example.com/{lid}",
            listing_id=lid, search_term="test",
        ))
        conn = sqlite3.connect(str(temp_db.DB_PATH))
        conn.execute(
            "UPDATE listings SET found_at=datetime('now', ? || ' hours') WHERE listing_id=?",
            (f"-{hours}", lid),
        )
        conn.commit()
        conn.close()

    def test_loescht_alte_listings(self, temp_db):
        self._save_old(temp_db, "old-1", hours=25)
        deleted = temp_db.clear_listings_older_than(24)
        assert deleted == 1
        assert temp_db.get_listing_count() == 0

    def test_belaesst_neue_listings(self, temp_db):
        self._save_old(temp_db, "new-1", hours=1)
        deleted = temp_db.clear_listings_older_than(24)
        assert deleted == 0
        assert temp_db.get_listing_count() == 1

    def test_schont_favoriten(self, temp_db):
        self._save_old(temp_db, "fav-old", hours=25)
        db_id = next(x["id"] for x in temp_db.get_listings() if x["listing_id"] == "fav-old")
        temp_db.toggle_favorite(db_id)
        deleted = temp_db.clear_listings_older_than(24)
        assert deleted == 0
        assert temp_db.get_listing_count() == 1

    def test_dismissed_nach_loeschen(self, temp_db):
        self._save_old(temp_db, "dismiss-old", hours=25)
        temp_db.clear_listings_older_than(24)
        assert temp_db.is_dismissed("dismiss-old") is True

    def test_gibt_anzahl_zurueck(self, temp_db):
        self._save_old(temp_db, "count-1", hours=25)
        self._save_old(temp_db, "count-2", hours=25)
        deleted = temp_db.clear_listings_older_than(24)
        assert deleted == 2


class TestMigrationFramework:
    """Tests für das versionierte Migrations-Framework (_migrations-Tabelle)."""

    def _minimal_db(self, path):
        """Erstellt eine minimale 'alte' DB ohne neue Spalten."""
        import sqlite3
        conn = sqlite3.connect(str(path))
        conn.executescript("""
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, listing_id TEXT UNIQUE, platform TEXT,
                title TEXT, price TEXT, location TEXT, url TEXT,
                found_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE geocache (location_text TEXT PRIMARY KEY, lat REAL, lon REAL);
        """)
        conn.commit()
        conn.close()

    def test_migrations_tabelle_wird_angelegt(self, tmp_path, monkeypatch):
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_track.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        self._minimal_db(old_db)
        db.init_db()

        conn = sqlite3.connect(str(old_db))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "_migrations" in tables

    def test_jede_migration_wird_nur_einmal_ausgefuehrt(self, tmp_path, monkeypatch):
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_idem.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        self._minimal_db(old_db)

        # Zweimal init_db() aufrufen
        db.init_db()
        db.init_db()

        conn = sqlite3.connect(str(old_db))
        rows = conn.execute("SELECT name FROM _migrations").fetchall()
        conn.close()

        # Jeder Name darf nur einmal vorkommen
        names = [r[0] for r in rows]
        assert len(names) == len(set(names)), "Doppelte Migrations-Einträge gefunden"

    def test_migration_traegt_alle_namen_ein(self, tmp_path, monkeypatch):
        import sqlite3
        import app.database as db

        old_db = tmp_path / "mig_names.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        self._minimal_db(old_db)
        db.init_db()

        conn = sqlite3.connect(str(old_db))
        names = {r[0] for r in conn.execute("SELECT name FROM _migrations")}
        conn.close()
        # Die drei Kernmigrationen müssen eingetragen sein (mit vN_-Prefix)
        assert "v2_listings_columns" in names
        assert "v3_search_terms_max_price" in names
        assert "v1_settings_rename" in names


class TestEnsureIndexes:
    """Tests für _ensure_indexes(): Indexes werden auf vollständiger DB angelegt."""

    def test_indexes_werden_angelegt(self, tmp_path, monkeypatch):
        import sqlite3
        import app.database as db

        test_db = tmp_path / "idx.db"
        monkeypatch.setattr(db, "DB_PATH", test_db)
        db.init_db()

        conn = sqlite3.connect(str(test_db))
        indexes = {r[1] for r in conn.execute("PRAGMA index_list(listings)")}
        conn.close()
        assert "idx_listings_platform" in indexes
        assert "idx_listings_found_at" in indexes
        assert "idx_listings_notified_at" in indexes

    def test_keine_fehler_auf_alter_db_ohne_neue_spalten(self, tmp_path, monkeypatch):
        """_ensure_indexes() darf nicht abstürzen wenn Spalten fehlen."""
        import sqlite3
        import app.database as db

        old_db = tmp_path / "idx_old.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)
        # Minimale DB ohne is_favorite / notified_at
        conn = sqlite3.connect(str(old_db))
        conn.executescript("""
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, listing_id TEXT UNIQUE, platform TEXT,
                title TEXT, price TEXT, location TEXT, url TEXT,
                found_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE geocache (location_text TEXT PRIMARY KEY, lat REAL, lon REAL);
        """)
        conn.commit()
        conn.close()

        # Darf nicht werfen
        db.init_db()


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
        assert "notes" in cols
        assert "potential_duplicate" in cols

    def test_migration_search_terms_max_price(self, tmp_path, monkeypatch):
        """search_terms.max_price wird ergänzt wenn nicht vorhanden."""
        import sqlite3
        import app.database as db

        old_db = tmp_path / "old2.db"
        monkeypatch.setattr(db, "DB_PATH", old_db)

        conn = sqlite3.connect(str(old_db))
        conn.executescript("""
            CREATE TABLE search_terms (
                id INTEGER PRIMARY KEY, term TEXT UNIQUE, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, listing_id TEXT UNIQUE, platform TEXT,
                title TEXT, price TEXT, location TEXT, url TEXT,
                found_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE geocache (
                location_text TEXT PRIMARY KEY, lat REAL, lon REAL
            );
        """)
        conn.commit()
        conn.close()

        db.init_db()

        conn = sqlite3.connect(str(old_db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(search_terms)")}
        conn.close()
        assert "max_price" in cols


# ── Profile ───────────────────────────────────────────────────

class TestProfiles:

    def test_profile_anlegen_und_lesen(self, temp_db):
        pid = temp_db.create_profile("Kai", "🐣")
        assert isinstance(pid, int)
        profile = temp_db.get_profile(pid)
        assert profile["name"] == "Kai"
        assert profile["emoji"] == "🐣"
        assert profile["last_seen_at"] is None

    def test_get_profiles_leer(self, temp_db):
        assert temp_db.get_profiles() == []

    def test_get_profiles_mehrere(self, temp_db):
        temp_db.create_profile("Kai", "🐣")
        temp_db.create_profile("Lisa", "🌸")
        profiles = temp_db.get_profiles()
        assert len(profiles) == 2
        assert {p["name"] for p in profiles} == {"Kai", "Lisa"}

    def test_unbekanntes_profil_gibt_none(self, temp_db):
        assert temp_db.get_profile(9999) is None

    def test_profil_aktualisieren(self, temp_db):
        pid = temp_db.create_profile("Alt", "👤")
        temp_db.update_profile(pid, "Neu", "🎉")
        profile = temp_db.get_profile(pid)
        assert profile["name"] == "Neu"
        assert profile["emoji"] == "🎉"

    def test_profil_loeschen(self, temp_db):
        pid = temp_db.create_profile("Löschen", "❌")
        temp_db.delete_profile(pid)
        assert temp_db.get_profile(pid) is None
        assert temp_db.get_profiles() == []

    def test_last_seen_at_wird_aktualisiert(self, temp_db):
        pid = temp_db.create_profile("Test", "👤")
        assert temp_db.get_profile(pid)["last_seen_at"] is None
        temp_db.update_profile_last_seen(pid)
        assert temp_db.get_profile(pid)["last_seen_at"] is not None
