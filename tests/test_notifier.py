"""Tests für app/notifier.py: HTML/Text-Builder."""

import pytest
from dataclasses import asdict
from email.mime.text import MIMEText
from unittest.mock import patch, MagicMock

from app.notifier import _card_html, _html_from_dicts, _text_from_dicts, _smtp_send
from app.scrapers.base import Listing


def make_listing(**kwargs) -> Listing:
    defaults = dict(
        platform="Kleinanzeigen",
        title="Kinderwagen Testmarke",
        price="45 €",
        location="Dortmund",
        url="https://example.com/123",
        listing_id="test-123",
        search_term="kinderwagen",
        image_url="",
        is_free=False,
        distance_km=None,
    )
    defaults.update(kwargs)
    return Listing(**defaults)


def make_listing_dict(**kwargs) -> dict:
    defaults = dict(
        platform="Shpock",
        title="Babybett komplett",
        price="60 €",
        location="Köln",
        url="https://shpock.com/456",
        listing_id="shp-456",
        search_term="babybett",
        image_url="",
        is_free=False,
        distance_km=None,
        found_at="2024-06-01T14:00:00",
    )
    defaults.update(kwargs)
    return defaults


# ── _card_html ────────────────────────────────────────────────

class TestCardHtml:

    def test_enthält_titel(self):
        html = _card_html("Mein Titel", "Kleinanzeigen", "test", "50 €", "Dortmund", "https://x.com")
        assert "Mein Titel" in html

    def test_enthält_plattform(self):
        html = _card_html("Titel", "Shpock", "test", "10 €", "Hamburg", "https://x.com")
        assert "Shpock" in html

    def test_enthält_preis(self):
        html = _card_html("Titel", "Kleinanzeigen", "test", "99 €", "Berlin", "https://x.com")
        assert "99 €" in html

    def test_enthält_link(self):
        html = _card_html("Titel", "P", "t", "0", "Ort", "https://mein.link/123")
        assert "https://mein.link/123" in html

    def test_gratis_badge_sichtbar_wenn_is_free(self):
        html = _card_html("Titel", "P", "t", "0 €", "Ort", "https://x.com", is_free=True)
        assert "Gratis" in html

    def test_kein_gratis_badge_wenn_nicht_frei(self):
        html = _card_html("Titel", "P", "t", "50 €", "Ort", "https://x.com", is_free=False)
        assert "Gratis" not in html

    def test_entfernung_sichtbar_wenn_vorhanden(self):
        html = _card_html("Titel", "P", "t", "10 €", "Ort", "https://x.com", distance_km=23.7)
        assert "km entfernt" in html  # 23.7 wird zu "24 km entfernt" gerundet

    def test_kein_entfernungs_text_ohne_distanz(self):
        html = _card_html("Titel", "P", "t", "10 €", "Ort", "https://x.com", distance_km=None)
        assert "km entfernt" not in html

    def test_bild_tag_wenn_bild_vorhanden(self):
        html = _card_html("T", "P", "s", "1 €", "O", "https://x.com", image_url="https://img.com/x.jpg")
        assert '<img' in html
        assert "https://img.com/x.jpg" in html

    def test_kein_bild_tag_ohne_bild(self):
        html = _card_html("T", "P", "s", "1 €", "O", "https://x.com", image_url="")
        assert '<img' not in html

    def test_datum_sichtbar_im_digest_modus(self):
        html = _card_html("T", "P", "s", "1 €", "O", "https://x.com",
                           found_at="2024-06-01T14:00:00", is_digest=True)
        assert "2024" in html

    def test_kein_datum_ohne_digest_modus(self):
        html = _card_html("T", "P", "s", "1 €", "O", "https://x.com",
                           found_at="2024-06-01T14:00:00", is_digest=False)
        assert "2024-06-01" not in html


# ── _html_from_dicts (Listing-Objekte) ───────────────────────

class TestHtmlFromObjects:

    def test_enthält_alle_titel(self):
        listings = [asdict(make_listing(title="Kinderwagen Alpha", listing_id="a1")),
                    asdict(make_listing(title="Babybett Beta", listing_id="b2"))]
        html = _html_from_dicts(listings)
        assert "Kinderwagen Alpha" in html
        assert "Babybett Beta" in html

    def test_korrekte_anzahl_im_heading(self):
        listings = [asdict(make_listing(listing_id=f"x{i}")) for i in range(3)]
        html = _html_from_dicts(listings)
        assert "3" in html

    def test_valides_html_grundstruktur(self):
        html = _html_from_dicts([asdict(make_listing())])
        assert html.startswith("<html>")
        assert "</html>" in html

    def test_leere_liste_kein_fehler(self):
        html = _html_from_dicts([])
        assert "<html>" in html


# ── _html_from_dicts ──────────────────────────────────────────

class TestHtmlFromDicts:

    def test_enthält_titel_aus_dict(self):
        listings = [make_listing_dict(title="Babyschale Top")]
        html = _html_from_dicts(listings)
        assert "Babyschale Top" in html

    def test_gratis_badge_aus_dict(self):
        listings = [make_listing_dict(is_free=True)]
        html = _html_from_dicts(listings)
        assert "Gratis" in html

    def test_leere_liste_kein_fehler(self):
        html = _html_from_dicts([])
        assert "<html>" in html


# ── _text_from_dicts (Listing-Objekte) ───────────────────────

class TestTextFromObjects:

    def test_enthält_plattform_und_titel(self):
        listings = [asdict(make_listing(title="Laufstall", platform="Kleinanzeigen"))]
        text = _text_from_dicts(listings)
        assert "Kleinanzeigen" in text
        assert "Laufstall" in text

    def test_gratis_kennzeichnung(self):
        listings = [asdict(make_listing(is_free=True))]
        text = _text_from_dicts(listings)
        assert "GRATIS" in text

    def test_entfernung_in_text(self):
        listings = [asdict(make_listing(distance_km=42.0))]
        text = _text_from_dicts(listings)
        assert "42" in text

    def test_url_enthalten(self):
        listings = [asdict(make_listing(url="https://mein.link/xyz"))]
        text = _text_from_dicts(listings)
        assert "https://mein.link/xyz" in text


# ── _text_from_dicts ──────────────────────────────────────────

class TestTextFromDicts:

    def test_enthält_plattform_und_titel(self):
        listings = [make_listing_dict(title="Hochstuhl", platform="Shpock")]
        text = _text_from_dicts(listings)
        assert "Shpock" in text
        assert "Hochstuhl" in text

    def test_gratis_kennzeichnung(self):
        listings = [make_listing_dict(is_free=True)]
        text = _text_from_dicts(listings)
        assert "GRATIS" in text


# ── _smtp_send ────────────────────────────────────────────────

class TestSmtpSend:

    def _make_msg(self):
        msg = MIMEText("test", "plain", "utf-8")
        msg["Subject"] = "Test"
        msg["From"] = "a@example.com"
        msg["To"] = "b@example.com"
        return msg

    def _mock_smtp(self):
        mock_ctx = MagicMock()
        mock_smtp = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        return mock_smtp, mock_ctx

    def test_leerer_port_string_verwendet_fallback_587(self):
        """Leerer smtp_port-String darf keinen ValueError auslösen."""
        mock_smtp, _ = self._mock_smtp()
        settings = {"email_smtp_server": "smtp.example.com", "email_smtp_port": ""}
        with patch("smtplib.SMTP", mock_smtp):
            _smtp_send(self._make_msg(), "a@example.com", "pw", ["b@example.com"], settings)
        mock_smtp.assert_called_with("smtp.example.com", 587)

    def test_gueltiger_port_wird_verwendet(self):
        mock_smtp, _ = self._mock_smtp()
        settings = {"email_smtp_server": "smtp.example.com", "email_smtp_port": "465"}
        with patch("smtplib.SMTP", mock_smtp):
            _smtp_send(self._make_msg(), "a@example.com", "pw", ["b@example.com"], settings)
        mock_smtp.assert_called_with("smtp.example.com", 465)

    def test_fehlende_port_einstellung_verwendet_fallback_587(self):
        mock_smtp, _ = self._mock_smtp()
        settings = {"email_smtp_server": "smtp.example.com"}
        with patch("smtplib.SMTP", mock_smtp):
            _smtp_send(self._make_msg(), "a@example.com", "pw", ["b@example.com"], settings)
        mock_smtp.assert_called_with("smtp.example.com", 587)
