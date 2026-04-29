"""Playwright UI-Tests für kritische Frontend-Features.

Einmalige Voraussetzung nach `pip install -r requirements.txt`:
    playwright install chromium

Ausführen:
    pytest tests/test_ui.py
    pytest tests/test_ui.py --headed          # sichtbarer Browser
    pytest tests/test_ui.py -k test_mehr_laden # einzelner Test
"""

import pytest
from playwright.sync_api import Page, expect


# ═══════════════════════════════════════════════════════════════
# Prio 1 – App wird unbrauchbar wenn kaputt
# ═══════════════════════════════════════════════════════════════

class TestDashboardUI:

    def test_dashboard_ladet_mit_listing_karten(self, page: Page, live_server: str):
        """Dashboard rendert mindestens eine Anzeigenkarte."""
        page.goto(live_server)
        expect(page.locator("#listings-grid")).to_be_visible()
        expect(page.locator(".listing-card").first).to_be_visible()

    def test_mehr_laden_button_sichtbar_bei_vielen_listings(self, page: Page, live_server: str):
        """Regression: Button blieb versteckt wenn server-seitig <PAGE_SIZE Karten gerendert wurden.

        35 Listings in DB → Server rendert 30 → Button muss trotzdem sichtbar sein.
        """
        page.goto(live_server)
        expect(page.locator("#load-more-btn")).to_be_visible()

    def test_mehr_laden_laedt_weitere_karten(self, page: Page, live_server: str):
        """Klick auf 'Mehr laden' erhöht die Anzahl der Karten im Grid."""
        page.goto(live_server)
        initial = page.locator(".listing-card").count()
        page.locator("#load-more-btn").click()
        page.wait_for_function(
            f"document.querySelectorAll('.listing-card').length > {initial}"
        )
        assert page.locator(".listing-card").count() > initial

    def test_crawl_button_zeigt_feedback(self, page: Page, live_server: str):
        """Klick auf 'Jetzt crawlen' zeigt sofort eine Statusmeldung."""
        page.goto(live_server)
        page.locator("#crawl-btn-top").click()
        expect(page.locator("#crawl-msg")).to_be_visible()


# ═══════════════════════════════════════════════════════════════
# Prio 2 – Stiller Datenverlust oder falsche Ergebnisse
# ═══════════════════════════════════════════════════════════════

class TestDismissUI:

    def test_dismiss_entfernt_karte_aus_dom(self, page: Page, live_server: str):
        """Klick auf ✕ entfernt die Karte sofort aus dem DOM."""
        page.goto(live_server)
        initial = page.locator(".listing-card").count()
        assert initial > 0
        page.locator("[aria-label='Anzeige ausblenden']").first.click()
        expect(page.locator(".listing-card")).to_have_count(initial - 1)

    def test_dismisste_anzeige_erscheint_nicht_nach_reload(self, page: Page, live_server: str):
        """Nach Reload taucht eine dismisste Anzeige nicht wieder auf."""
        page.goto(live_server)
        first_card = page.locator(".listing-card").first
        card_id = first_card.get_attribute("data-id")
        first_card.locator("[aria-label='Anzeige ausblenden']").click()
        page.reload()
        expect(page.locator(f".listing-card[data-id='{card_id}']")).to_have_count(0)


class TestSuchbegriffeUI:

    def test_suchbegriff_hinzufuegen_erscheint_in_sidebar(self, page: Page, live_server: str):
        """Neuer Suchbegriff ist nach Form-Submit in der Sidebar sichtbar."""
        page.goto(live_server)
        term_input = page.locator("input[name='term']")
        term_input.fill("spielzeug")
        term_input.press("Enter")
        # term-filter-btn ist der Filter-Button (nicht der Löschen-Button)
        expect(page.locator("button.term-filter-btn[data-term='spielzeug']")).to_be_visible()

    def test_suchbegriff_loeschen_entfernt_aus_sidebar(self, page: Page, live_server: str):
        """Gelöschter Begriff verschwindet aus der Sidebar."""
        page.goto(live_server)
        page.locator("input[name='term']").fill("zulöschen")
        page.locator("input[name='term']").press("Enter")
        expect(page.locator("button.term-filter-btn[data-term='zulöschen']")).to_be_visible()

        # Löschen: JS-Button öffnet Custom-Confirm-Modal → #confirm-ok-btn bestätigen
        page.locator("button[aria-label*=\"zulöschen' löschen\"]").click()
        expect(page.locator("#confirm-modal")).to_be_visible()
        page.locator("#confirm-ok-btn").click()
        # Nach Form-Submit und Redirect taucht der Term nicht mehr auf
        expect(page.locator("button.term-filter-btn[data-term='zulöschen']")).to_have_count(0)


class TestFilterUI:

    def test_term_filter_aktiviert_filter_label(self, page: Page, live_server: str):
        """Klick auf einen Term-Button zeigt das Filter-Label an."""
        page.goto(live_server)
        first_btn = page.locator("button[data-term]").first
        term = first_btn.get_attribute("data-term")
        first_btn.click()
        page.wait_for_timeout(500)
        expect(page.locator("#filter-label")).to_be_visible()
        expect(page.locator("#filter-label")).to_contain_text(term)

    def test_filter_zuruecksetzen_blendet_label_aus(self, page: Page, live_server: str):
        """Klick auf 'Filter zurücksetzen' entfernt aktive Filter und Label."""
        page.goto(live_server)
        page.locator("button[data-term]").first.click()
        page.wait_for_timeout(400)
        expect(page.locator("#filter-label")).to_be_visible()

        page.locator("#filter-clear").click()
        page.wait_for_timeout(400)
        # #filter-label bleibt im DOM, bekommt aber die 'hidden'-Klasse (display:none)
        expect(page.locator("#filter-label")).not_to_be_visible()


class TestApiSchemaUI:

    def test_api_listings_liefert_pflichtfelder(self, page: Page, live_server: str):
        """/api/listings liefert alle Felder, auf die das JS zugreift."""
        resp = page.request.get(f"{live_server}/api/listings?limit=1")
        assert resp.status == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            for field in ("id", "title", "platform", "price", "url", "found_at",
                          "is_favorite", "is_free", "search_term"):
                assert field in item, f"Pflichtfeld '{field}' fehlt in /api/listings"

    def test_api_status_liefert_pflichtfelder(self, page: Page, live_server: str):
        """/api/status liefert alle Felder für die Plattform-Tabelle im Dashboard."""
        resp = page.request.get(f"{live_server}/api/status")
        assert resp.status == 200
        data = resp.json()
        for field in ("crawl_status", "platforms", "total_listings"):
            assert field in data, f"Pflichtfeld '{field}' fehlt in /api/status"
        assert isinstance(data["platforms"], list)
        if data["platforms"]:
            p = data["platforms"][0]
            for field in ("id", "display", "enabled", "is_running"):
                assert field in p, f"Plattform-Pflichtfeld '{field}' fehlt"


# ═══════════════════════════════════════════════════════════════
# Prio 3 – UI-Details
# ═══════════════════════════════════════════════════════════════

class TestFavoritenUI:

    def test_favorit_toggeln_und_nach_reload_erhalten(self, page: Page, live_server: str):
        """Favorit wird nach Server-Reload als Favorit angezeigt (gelber Stern)."""
        page.goto(live_server)
        fav_btn = page.locator("button[aria-label='Als Favorit markieren']").first
        fav_btn.click()
        page.wait_for_timeout(500)
        page.reload()
        expect(page.locator("button[aria-label='Favorit entfernen']").first).to_be_visible()

    def test_favorit_steht_nach_reload_ganz_oben(self, page: Page, live_server: str):
        """Favorisierte Karte ist nach Reload an erster Stelle (ORDER BY is_favorite DESC)."""
        page.goto(live_server)
        first_card = page.locator(".listing-card").first
        card_id = first_card.get_attribute("data-id")
        first_card.locator("button[aria-label='Als Favorit markieren']").click()
        page.wait_for_timeout(500)
        page.reload()
        new_first_id = page.locator(".listing-card").first.get_attribute("data-id")
        assert new_first_id == card_id


class TestSettingsUI:

    def test_settings_seite_ladet(self, page: Page, live_server: str):
        """Settings-Seite rendert mit allen Tab-Buttons."""
        page.goto(f"{live_server}/settings")
        for tab in ("platforms", "notifications", "crawler", "ai", "profiles", "data"):
            expect(page.locator(f"button[data-tab='{tab}']")).to_be_visible()

    def test_alle_tabs_zeigen_ihr_panel(self, page: Page, live_server: str):
        """Klick auf jeden Tab macht das zugehörige Panel sichtbar."""
        page.goto(f"{live_server}/settings")
        for tab in ("notifications", "crawler", "ai", "profiles", "data", "platforms"):
            page.locator(f"button[data-tab='{tab}']").click()
            expect(page.locator(f"#tab-{tab}")).to_be_visible()

    def test_settings_speichern_zeigt_erfolgsmeldung(self, page: Page, live_server: str):
        """Form-Submit leitet zurück und zeigt eine Flash-Meldung."""
        page.goto(f"{live_server}/settings")
        page.locator("button[type='submit']").last.click()
        expect(page).to_have_url(f"{live_server}/settings")
        # Flash-Meldung (success oder info) muss sichtbar sein
        expect(page.locator(".bg-green-50, .bg-yellow-50, .bg-red-50").first).to_be_visible()


class TestProfilUI:

    def test_profil_auswahl_flow(self, page: Page, live_server: str):
        """Mit existierendem Profil: Redirect zur Auswahl, Profil wählen, zurück zum Dashboard."""
        import app.database as db_module
        db_module.create_profile("Testperson", "🧸")

        page.goto(live_server)
        expect(page).to_have_url(f"{live_server}/profiles/select")

        # Profil-Karte klicken (Submit im POST-Form)
        page.locator("form[action*='/profiles/select/'] button").first.click()
        page.wait_for_url(live_server + "/")
        expect(page.locator("#listings-grid")).to_be_visible()

    def test_profil_name_in_navbar_nach_auswahl(self, page: Page, live_server: str):
        """Aktiver Profilname ist nach der Auswahl in der Navbar sichtbar."""
        import app.database as db_module
        db_module.create_profile("Kai", "👶")

        page.goto(f"{live_server}/profiles/select")
        page.locator("form[action*='/profiles/select/'] button").first.click()
        page.wait_for_url(live_server + "/")
        expect(page.locator("nav, header")).to_contain_text("Kai")
