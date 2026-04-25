"""Tests für VintedScraper, ShpockScraper und EbayScraper."""

from unittest.mock import MagicMock, patch

import pytest

from app.scrapers.base import Listing
from app.scrapers.ebay import EbayScraper
from app.scrapers.shpock import ShpockScraper
from app.scrapers.vinted import VintedScraper


def _mock_response(json_data=None, text="", status=200):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    return r


def _ebay_page(items_html: str) -> str:
    return f'<html><body><ul class="srp-results">{items_html}</ul></body></html>'


# ── Vinted ────────────────────────────────────────────────────────────────────

VINTED_ITEM = {
    "id": 99,
    "title": "Babywanne Hauck",
    "price": {"amount": "15.0", "currency_code": "EUR"},
    "url": "https://www.vinted.de/items/99-babywanne",
    "description": "Top Zustand",
    "user": {"city": "Berlin"},
    "photo": {"url": "https://cdn.vinted.de/img/99.jpg"},
}


class TestVintedScraper:

    def _scraper(self, settings=None):
        return VintedScraper(settings or {})

    def test_search_gibt_listings_zurueck(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", return_value=_mock_response({"items": [VINTED_ITEM]})):
            results = scraper.search("babywanne", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Babywanne Hauck"

    def test_search_leere_antwort(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", return_value=_mock_response({"items": []})):
            assert scraper.search("babywanne") == []

    def test_search_bei_exception(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", side_effect=Exception("Netzwerkfehler")):
            assert scraper.search("babywanne") == []

    def test_parse_felder(self):
        scraper = self._scraper()
        listing = scraper._parse(VINTED_ITEM, "babywanne")
        assert listing.platform == "Vinted"
        assert listing.listing_id == "vt_99"
        assert listing.price == "15.00 €"
        assert listing.location == "Berlin"
        assert listing.url == "https://www.vinted.de/items/99-babywanne"
        assert listing.image_url == "https://cdn.vinted.de/img/99.jpg"
        assert listing.search_term == "babywanne"
        assert listing.description == "Top Zustand"

    def test_parse_fehlende_felder_kein_absturz(self):
        scraper = self._scraper()
        listing = scraper._parse({}, "test")
        assert listing is not None
        assert listing.listing_id == "vt_"

    def test_parse_ohne_foto(self):
        scraper = self._scraper()
        listing = scraper._parse({**VINTED_ITEM, "photo": None}, "test")
        assert listing.image_url == ""

    def test_parse_preis_in_nested_struktur(self):
        scraper = self._scraper()
        item = {**VINTED_ITEM, "price": None, "total_item_price": {"amount": "20"}}
        listing = scraper._parse(item, "test")
        assert listing.price == "20.00 €"

    def test_parse_kein_preis_ergibt_ka(self):
        scraper = self._scraper()
        listing = scraper._parse({**VINTED_ITEM, "price": None}, "test")
        assert listing.price == "k.A."

    def test_max_price_wird_gesetzt(self):
        scraper = VintedScraper({"vinted_max_price": "30"})
        assert scraper.max_price == 30.0

    def test_max_price_ungueltig_wird_ignoriert(self):
        scraper = VintedScraper({"vinted_max_price": "abc"})
        assert scraper.max_price is None

    def test_search_sendet_max_price_parameter(self):
        scraper = VintedScraper({"vinted_max_price": "25"})
        with patch.object(scraper.session, "get", return_value=_mock_response({"items": []})) as mock_get:
            scraper.search("babywanne")
        params = mock_get.call_args[1]["params"]
        assert params["price_to"] == 25.0

    def test_authenticate_wird_im_init_aufgerufen(self):
        with patch.object(VintedScraper, "_authenticate") as mock_auth:
            VintedScraper({})
        mock_auth.assert_called_once()

    def test_401_loest_reauth_und_retry_aus(self):
        scraper = VintedScraper({})
        response_401 = _mock_response(status=401)
        response_401.raise_for_status.side_effect = Exception("401")
        response_ok = _mock_response({"items": []})
        with patch.object(scraper.session, "get", side_effect=[response_401, response_ok, response_ok]) as mock_get:
            scraper.search("babywanne")
        # Erster Call: API (401), zweiter: _authenticate (Homepage), dritter: API-Retry
        assert mock_get.call_count == 3

    def test_parse_preis_als_dict(self):
        scraper = VintedScraper({})
        item = {**VINTED_ITEM, "price": {"amount": "9.5", "currency_code": "EUR"}}
        listing = scraper._parse(item, "test")
        assert listing.price == "9.50 €"


# ── Shpock ────────────────────────────────────────────────────────────────────

SHPOCK_ITEM = {
    "__typename": "ItemSummary",
    "id": "abc123",
    "title": "Babytrage Ergobaby",
    "description": "Wenig benutzt",
    "price": 45,
    "isFree": False,
    "isSold": False,
    "locality": "44135 Dortmund",
    "distance": None,
    "distanceUnit": None,
    "path": "/de-de/i/abc123/babytrage",
    "media": [{"id": "deadbeef01234567890abcde"}],
}


class TestShpockScraper:

    def _scraper(self, settings=None):
        return ShpockScraper(settings or {
            "shpock_max_price": "100",
            "shpock_radius": "30",
            "shpock_latitude": "51.5136",
            "shpock_longitude": "7.4653",
        })

    def _api_response(self, items):
        return {"data": {"itemSearch": {"itemResults": [{"items": items}]}}}

    def test_parse_felder(self):
        scraper = self._scraper()
        listing = scraper._parse(SHPOCK_ITEM, "babytrage")
        assert listing.platform == "Shpock"
        assert listing.listing_id == "sp_abc123"
        assert listing.title == "Babytrage Ergobaby"
        assert listing.price == "45.00 €"
        assert listing.location == "44135 Dortmund"
        assert listing.url == "https://www.shpock.com/de-de/i/abc123/babytrage"
        assert listing.image_url == "https://m1.secondhandapp.at/full/deadbeef01234567890abcde"
        assert listing.search_term == "babytrage"

    def test_parse_is_free(self):
        scraper = self._scraper()
        item = {**SHPOCK_ITEM, "isFree": True, "price": 0}
        listing = scraper._parse(item, "test")
        assert listing.price == "0 €"

    def test_parse_ohne_media(self):
        scraper = self._scraper()
        listing = scraper._parse({**SHPOCK_ITEM, "media": []}, "test")
        assert listing.image_url == ""

    def test_search_filtert_verkaufte_items(self):
        scraper = self._scraper()
        sold = {**SHPOCK_ITEM, "isSold": True}
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([sold]))):
            with patch("app.scrapers.shpock.geocode", return_value=(51.5136, 7.4653)):
                results = scraper.search("babytrage")
        assert results == []

    def test_search_filtert_nach_max_price(self):
        scraper = self._scraper({"shpock_max_price": "30", "shpock_radius": "200",
                                  "shpock_latitude": "51.5136", "shpock_longitude": "7.4653"})
        teuer = {**SHPOCK_ITEM, "price": 50}
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([teuer]))):
            with patch("app.scrapers.shpock.geocode", return_value=(51.5136, 7.4653)):
                results = scraper.search("babytrage")
        assert results == []

    def test_search_filtert_nach_radius(self):
        scraper = self._scraper()  # radius=30 km, Dortmund
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([SHPOCK_ITEM]))):
            # München liegt ~470 km entfernt
            with patch("app.scrapers.shpock.geocode", return_value=(48.1372, 11.5755)):
                results = scraper.search("babytrage")
        assert results == []

    def test_search_gibt_treffer_im_radius_zurueck(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "post", return_value=_mock_response(self._api_response([SHPOCK_ITEM]))):
            # Dortmund-Mitte: innerhalb 30 km
            with patch("app.scrapers.shpock.geocode", return_value=(51.5200, 7.4800)):
                results = scraper.search("babytrage")
        assert len(results) == 1
        assert results[0].title == "Babytrage Ergobaby"

    def test_search_bei_api_fehler(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "post", side_effect=Exception("Timeout")):
            assert scraper.search("babytrage") == []

    def test_search_bei_graphql_fehler(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "post", return_value=_mock_response({"errors": [{"message": "oops"}]})):
            assert scraper.search("babytrage") == []


# ── eBay ──────────────────────────────────────────────────────────────────────

EBAY_ITEM_HTML = """
<li class="s-item">
  <a class="s-item__link" href="https://www.ebay.de/itm/123456789?_trkparms=test">
    <h3 class="s-item__title">Kinderwagen Bugaboo</h3>
  </a>
  <span class="s-item__price">80,00\xa0€</span>
  <span class="s-item__location">Standort:\xa0Hamburg</span>
  <img class="s-item__image-img" src="https://i.ebayimg.com/img/123.jpg" />
</li>
"""

EBAY_PLACEHOLDER_HTML = """
<li class="s-item s-item--placeholder">
  <span class="s-item__title">Shop on eBay</span>
</li>
"""


class TestEbayScraper:

    def _scraper(self, settings=None):
        return EbayScraper(settings or {})

    def test_search_gibt_listings_zurueck(self):
        scraper = self._scraper()
        html = _ebay_page(EBAY_ITEM_HTML)
        with patch.object(scraper.session, "get", return_value=_mock_response(text=html)):
            results = scraper.search("kinderwagen", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Kinderwagen Bugaboo"

    def test_placeholder_wird_ignoriert(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", return_value=_mock_response(text=_ebay_page(EBAY_PLACEHOLDER_HTML))):
            assert scraper.search("kinderwagen") == []

    def test_search_bei_exception(self):
        scraper = self._scraper()
        with patch.object(scraper.session, "get", side_effect=Exception("Timeout")):
            assert scraper.search("kinderwagen") == []

    def test_parse_felder(self):
        from bs4 import BeautifulSoup
        scraper = self._scraper()
        item = BeautifulSoup(EBAY_ITEM_HTML, "lxml").select_one("li.s-item")
        listing = scraper._parse(item, "kinderwagen")
        assert listing.platform == "eBay"
        assert listing.title == "Kinderwagen Bugaboo"
        assert listing.listing_id == "eb_123456789"
        assert listing.location == "Hamburg"
        assert listing.image_url == "https://i.ebayimg.com/img/123.jpg"
        assert listing.search_term == "kinderwagen"

    def test_build_url_enkodiert_leerzeichen(self):
        scraper = self._scraper()
        assert "baby+stuhl" in scraper._build_url("baby stuhl", 20)

    def test_build_url_enthaelt_neuheits_sortierung(self):
        scraper = self._scraper()
        assert "_sop=10" in scraper._build_url("test", 20)

    def test_price_ok_unter_max(self):
        scraper = EbayScraper({"ebay_max_price": "100"})
        listing = Listing("eBay", "Test", "80,00 €", "", "", "eb_1", "test")
        assert scraper._price_ok(listing) is True

    def test_price_ok_ueber_max(self):
        scraper = EbayScraper({"ebay_max_price": "50"})
        listing = Listing("eBay", "Test", "80,00 €", "", "", "eb_1", "test")
        assert scraper._price_ok(listing) is False

    def test_price_ok_ohne_max_immer_true(self):
        scraper = self._scraper()
        listing = Listing("eBay", "Test", "999,00 €", "", "", "eb_1", "test")
        assert scraper._price_ok(listing) is True

    def test_price_ok_ka_wird_durchgelassen(self):
        scraper = EbayScraper({"ebay_max_price": "50"})
        listing = Listing("eBay", "Test", "k.A.", "", "", "eb_1", "test")
        assert scraper._price_ok(listing) is True

    def test_max_price_ungueltig_wird_ignoriert(self):
        scraper = EbayScraper({"ebay_max_price": "abc"})
        assert scraper.max_price is None
