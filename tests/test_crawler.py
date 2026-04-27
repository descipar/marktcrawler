"""Tests für app/crawler.py: _is_free() und _is_blacklisted()."""

import pytest
from app.crawler import _is_free, _is_blacklisted
from app.scrapers.base import Listing


def make_listing(**kwargs) -> Listing:
    """Hilfsfunktion: Listing mit sinnvollen Defaults erstellen."""
    defaults = dict(
        platform="Test",
        title="Kinderwagen",
        price="50 €",
        location="Dortmund",
        url="https://example.com/1",
        listing_id="test-1",
        search_term="kinderwagen",
        description="",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


# ── _is_free ─────────────────────────────────────────────────

class TestIsFree:

    # --- Preis-Erkennung ---

    def test_preis_null_euro(self):
        assert _is_free(make_listing(price="0 €")) is True

    def test_preis_null_euro_ohne_space(self):
        assert _is_free(make_listing(price="0€")) is True

    def test_preis_null_komma_null(self):
        assert _is_free(make_listing(price="0,00 €")) is True

    def test_preis_kostenlos(self):
        assert _is_free(make_listing(price="Kostenlos")) is True

    def test_preis_kostenlos_kleinschreibung(self):
        assert _is_free(make_listing(price="kostenlos")) is True

    def test_preis_gratis(self):
        assert _is_free(make_listing(price="Gratis")) is True

    def test_preis_umsonst(self):
        assert _is_free(make_listing(price="umsonst")) is True

    def test_preis_zu_verschenken(self):
        assert _is_free(make_listing(price="zu verschenken")) is True

    def test_preis_free(self):
        assert _is_free(make_listing(price="free")) is True

    def test_normaler_preis_nicht_frei(self):
        assert _is_free(make_listing(price="50 €")) is False

    def test_preis_mit_fuehrendem_nullen_nicht_frei(self):
        """'01 €' ist kein Gratis-Angebot."""
        assert _is_free(make_listing(price="01 €")) is False

    # --- Titel-Erkennung ---

    def test_titel_zu_verschenken(self):
        assert _is_free(make_listing(title="Kinderwagen zu verschenken", price="")) is True

    def test_titel_verschenke(self):
        assert _is_free(make_listing(title="Verschenke Babywippe", price="")) is True

    def test_titel_gratis(self):
        assert _is_free(make_listing(title="Babyschale gratis abzugeben", price="")) is True

    def test_titel_zu_vergeben(self):
        assert _is_free(make_listing(title="Babybett zu vergeben", price="")) is True

    # --- Beschreibungs-Erkennung ---

    def test_beschreibung_kostenlos(self):
        listing = make_listing(price="VB", description="Ist kostenlos, einfach abholen")
        assert _is_free(listing) is True

    def test_beschreibung_zu_verschenken(self):
        # Echter Preis schlägt Text: 5 € → nicht gratis
        listing = make_listing(price="5 €", description="Wir geben es lieber zu verschenken")
        assert _is_free(listing) is False

    # --- Kein False Positive ---

    def test_normales_listing_nicht_frei(self):
        listing = make_listing(
            title="Guter Kinderwagen Maxi-Cosi",
            price="80 €",
            description="Wenig benutzt, guter Zustand",
        )
        assert _is_free(listing) is False

    def test_preis_mit_gratis_in_beschreibung_nicht_frei(self):
        """44 € + 'gratis Zubehör dabei' in Beschreibung → nicht gratis (Original-Bug)."""
        listing = make_listing(price="44.00 €", description="Inkl. gratis Zubehör dabei")
        assert _is_free(listing) is False

    def test_vb_preis_mit_kostenlos_in_beschreibung_ist_frei(self):
        """VB ist kein echter Preis → Beschreibung 'kostenlos' zählt."""
        listing = make_listing(price="VB", description="Ist kostenlos, einfach abholen")
        assert _is_free(listing) is True

    def test_leerer_preis_kein_fehler(self):
        """Leerer Preis darf keinen Exception werfen."""
        assert _is_free(make_listing(price="")) is False

    def test_keiner_angabe_preis(self):
        assert _is_free(make_listing(price="k.A.")) is False


# ── _is_blacklisted ───────────────────────────────────────────

class TestIsBlacklisted:

    def test_leere_blacklist_nie_blacklisted(self):
        assert _is_blacklisted(make_listing(title="defekter Kinderwagen"), []) is False

    def test_wort_im_titel_wird_erkannt(self):
        assert _is_blacklisted(make_listing(title="Kinderwagen defekt"), ["defekt"]) is True

    def test_wort_in_beschreibung_wird_erkannt(self):
        listing = make_listing(description="Für Bastler geeignet")
        assert _is_blacklisted(listing, ["bastler"]) is True

    def test_grossschreibung_wird_ignoriert(self):
        assert _is_blacklisted(make_listing(title="DEFEKTER Kinderwagen"), ["defekt"]) is True

    def test_blacklist_grossschreibung_wird_ignoriert(self):
        assert _is_blacklisted(make_listing(title="defekter Kinderwagen"), ["DEFEKT"]) is True

    def test_substring_match(self):
        """Blacklist prüft Teilstring: 'ersatz' trifft auch 'Ersatzteil'."""
        assert _is_blacklisted(make_listing(title="Ersatzteil"), ["ersatz"]) is True
        # Umgekehrt: 'ersatzteile' trifft kein Listing ohne dieses Wort
        assert _is_blacklisted(make_listing(title="guter Kinderwagen"), ["ersatzteile"]) is False

    def test_mehrere_blacklist_worter(self):
        assert _is_blacklisted(make_listing(title="Kinderwagen"), ["defekt", "kinderwagen"]) is True

    def test_kein_match_bei_unbekanntem_wort(self):
        assert _is_blacklisted(make_listing(title="Sehr guter Zustand"), ["defekt", "bastler"]) is False

    def test_zeilenumbruch_separierte_blacklist(self):
        """Blacklist kann auch mit Zeilenumbrüchen übergeben werden (nach Parse durch Crawler)."""
        # crawler.py splittet schon vor dem Aufruf – hier testen wir die bereits geparste Liste
        blacklist = ["defekt", "bastler", "kaputt"]
        assert _is_blacklisted(make_listing(title="kaputtes Babybett"), blacklist) is True

    def test_leerzeichen_in_blacklist_eintrag(self):
        """Mehrteilige Blacklist-Einträge funktionieren."""
        assert _is_blacklisted(
            make_listing(title="Kinderwagen zu reparieren"),
            ["zu reparieren"],
        ) is True
