"""Tests für app/notifier.py: HTML/Text-Builder."""

import pytest
from dataclasses import asdict
from email.mime.text import MIMEText
from unittest.mock import patch, MagicMock

from app.notifier import (
    _card_html, _html_from_dicts, _html_grouped, _html_email, _text_from_dicts, _smtp_send,
    notify, notify_pending, send_digest, _get_email_config, _normalize_server_url,
)
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

    def test_html_sonderzeichen_werden_escaped(self):
        """Listing-Daten mit HTML/JS dürfen nicht ungefiltert ins Email-HTML."""
        xss = '<script>alert("xss")</script>'
        html = _card_html(xss, "P", xss, xss, xss, "https://x.com")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


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


# ── _html_grouped ────────────────────────────────────────────

class TestHtmlGrouped:

    def _two_platform_listings(self):
        return [
            make_listing_dict(platform="Kleinanzeigen", search_term="kinderwagen", title="Wagen A", listing_id="a1"),
            make_listing_dict(platform="Kleinanzeigen", search_term="kinderwagen", title="Wagen B", listing_id="a2"),
            make_listing_dict(platform="Shpock", search_term="babybett", title="Bett X", listing_id="b1"),
        ]

    def test_valide_html_grundstruktur(self):
        html = _html_grouped([make_listing_dict()])
        assert html.startswith("<html>")
        assert "</html>" in html

    def test_enthält_alle_plattformen(self):
        html = _html_grouped(self._two_platform_listings())
        assert "Kleinanzeigen" in html
        assert "Shpock" in html

    def test_enthält_alle_titel(self):
        html = _html_grouped(self._two_platform_listings())
        assert "Wagen A" in html
        assert "Wagen B" in html
        assert "Bett X" in html

    def test_enthält_suchbegriffe(self):
        html = _html_grouped(self._two_platform_listings())
        assert "kinderwagen" in html
        assert "babybett" in html

    def test_enthält_gesamtanzahl(self):
        html = _html_grouped(self._two_platform_listings())
        assert "3" in html

    def test_gratis_hervorgehoben(self):
        listing = make_listing_dict(is_free=True)
        html = _html_grouped([listing])
        assert "Gratis" in html
        assert "#dcedc8" in html  # grüner Hintergrund für Gratis-Karten

    def test_leere_liste_kein_fehler(self):
        html = _html_grouped([])
        assert "<html>" in html

    def test_inhaltsverzeichnis_vorhanden(self):
        html = _html_grouped(self._two_platform_listings())
        assert "Inhalt" in html


# ── notify_pending ────────────────────────────────────────────

class TestNotifyPending:

    _SETTINGS = {
        "email_enabled": "1",
        "email_sender": "sender@example.com",
        "email_password": "pw",
        "email_recipient": "recv@example.com",
        "email_smtp_server": "smtp.example.com",
        "email_smtp_port": "587",
        "email_subject_alert": "🔍 Marktcrawler: {n} neue Anzeige(n) gefunden!",
    }

    def test_sendet_nicht_wenn_email_deaktiviert(self):
        settings = {**self._SETTINGS, "email_enabled": "0"}
        with patch("app.notifier.db.claim_unnotified_listings") as mock_claim:
            result = notify_pending(settings)
        assert result is False
        mock_claim.assert_not_called()

    def test_sendet_nicht_ohne_listings(self):
        with patch("app.notifier.db.claim_unnotified_listings", return_value=[]), \
             patch("app.notifier._smtp_send") as mock_smtp:
            result = notify_pending(self._SETTINGS)
        assert result is False
        mock_smtp.assert_not_called()

    def test_loggt_nach_versand(self):
        """Nach erfolgreichem Versand wird log_notification aufgerufen (keine mark-Pflicht mehr)."""
        listings = [
            {**make_listing_dict(listing_id="p1"), "listing_id": "p1"},
            {**make_listing_dict(listing_id="p2"), "listing_id": "p2"},
        ]
        with patch("app.notifier.db.claim_unnotified_listings", return_value=listings), \
             patch("app.notifier.db.get_profiles", return_value=[]), \
             patch("app.notifier._smtp_send", return_value=True), \
             patch("app.notifier.db.log_notification") as mock_log:
            result = notify_pending(self._SETTINGS)
        assert result is True
        mock_log.assert_called_once()

    def test_kein_log_bei_smtp_fehler(self):
        listings = [{**make_listing_dict(), "listing_id": "q1"}]
        with patch("app.notifier.db.claim_unnotified_listings", return_value=listings), \
             patch("app.notifier.db.get_profiles", return_value=[]), \
             patch("app.notifier._smtp_send", return_value=False), \
             patch("app.notifier.db.log_notification") as mock_log:
            result = notify_pending(self._SETTINGS)
        assert result is False
        mock_log.assert_not_called()

    def test_per_profil_sendet_an_profil_emails(self):
        listings = [{**make_listing_dict(), "listing_id": "pp-1"}]
        profiles = [
            {"email": "alice@example.com", "notify_mode": "immediate"},
            {"email": "bob@example.com", "notify_mode": "both"},
        ]
        with patch("app.notifier.db.claim_unnotified_listings", return_value=listings), \
             patch("app.notifier.db.get_profiles", return_value=profiles), \
             patch("app.notifier._send_dicts") as mock_send, \
             patch("app.notifier.db.log_notification"):
            result = notify_pending(self._SETTINGS)
        assert result is True
        assert mock_send.call_count == 2
        recipients = [call.kwargs.get("recipients") or call.args[3] for call in mock_send.call_args_list]
        assert ["alice@example.com"] in recipients
        assert ["bob@example.com"] in recipients

    def test_per_profil_ignoriert_stumme_profile(self):
        """Profile mit notify_mode=digest_only/off bekommen keinen Alert."""
        listings = [{**make_listing_dict(), "listing_id": "pp-2"}]
        profiles = [
            {"email": "carol@example.com", "notify_mode": "digest_only"},
            {"email": "dave@example.com", "notify_mode": "off"},
            {"email": None, "notify_mode": "immediate"},
        ]
        with patch("app.notifier.db.claim_unnotified_listings", return_value=listings), \
             patch("app.notifier.db.get_profiles", return_value=profiles), \
             patch("app.notifier._smtp_send", return_value=True) as mock_smtp, \
             patch("app.notifier.db.log_notification"):
            result = notify_pending(self._SETTINGS)
        assert result is True
        # Kein Profil qualifiziert → Fallback auf globale Settings (ein SMTP-Aufruf)
        mock_smtp.assert_called_once()

    def test_per_profil_fallback_auf_globale_settings(self):
        """Wenn kein Profil eine E-Mail hat, gelten globale email_recipient-Settings."""
        listings = [{**make_listing_dict(), "listing_id": "pp-3"}]
        with patch("app.notifier.db.claim_unnotified_listings", return_value=listings), \
             patch("app.notifier.db.get_profiles", return_value=[]), \
             patch("app.notifier._smtp_send", return_value=True) as mock_smtp, \
             patch("app.notifier.db.log_notification"):
            result = notify_pending(self._SETTINGS)
        assert result is True
        mock_smtp.assert_called_once()


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

    def test_env_smtp_server_hat_vorrang(self, monkeypatch):
        """EMAIL_SMTP_SERVER env var überschreibt settings-Wert."""
        monkeypatch.setenv("EMAIL_SMTP_SERVER", "smtp.override.com")
        monkeypatch.setenv("EMAIL_SMTP_PORT", "465")
        mock_smtp, _ = self._mock_smtp()
        settings = {"email_smtp_server": "smtp.should-be-ignored.com", "email_smtp_port": "587"}
        with patch("smtplib.SMTP", mock_smtp):
            _smtp_send(self._make_msg(), "a@example.com", "pw", ["b@example.com"], settings)
        mock_smtp.assert_called_with("smtp.override.com", 465)


# ── _get_email_config: Env-Var-Priorität ─────────────────────

class TestGetEmailConfig:

    def test_db_werte_werden_verwendet(self, monkeypatch):
        monkeypatch.delenv("EMAIL_SENDER", raising=False)
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
        monkeypatch.delenv("EMAIL_RECIPIENT", raising=False)
        settings = {
            "email_sender": "db@example.com",
            "email_password": "db-pw",
            "email_recipient": "recv@example.com",
        }
        sender, pw, recipients = _get_email_config(settings)
        assert sender == "db@example.com"
        assert pw == "db-pw"
        assert recipients == ["recv@example.com"]

    def test_env_vars_haben_vorrang_vor_db(self, monkeypatch):
        monkeypatch.setenv("EMAIL_SENDER", "env@example.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "env-pw")
        monkeypatch.setenv("EMAIL_RECIPIENT", "env-recv@example.com")
        settings = {
            "email_sender": "db@example.com",
            "email_password": "db-pw",
            "email_recipient": "db-recv@example.com",
        }
        sender, pw, recipients = _get_email_config(settings)
        assert sender == "env@example.com"
        assert pw == "env-pw"
        assert recipients == ["env-recv@example.com"]

    def test_fehlende_konfiguration_gibt_leere_empfaengerliste(self, monkeypatch):
        monkeypatch.delenv("EMAIL_SENDER", raising=False)
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
        monkeypatch.delenv("EMAIL_RECIPIENT", raising=False)
        sender, pw, recipients = _get_email_config({})
        assert recipients == []

    def test_mehrere_empfaenger_kommagetrennt(self, monkeypatch):
        monkeypatch.delenv("EMAIL_SENDER", raising=False)
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
        monkeypatch.delenv("EMAIL_RECIPIENT", raising=False)
        settings = {
            "email_sender": "s@e.com",
            "email_password": "pw",
            "email_recipient": "a@e.com, b@e.com, c@e.com",
        }
        _, _, recipients = _get_email_config(settings)
        assert recipients == ["a@e.com", "b@e.com", "c@e.com"]


# ── _html_email direkt ────────────────────────────────────────

class TestHtmlEmail:
    """Direkter Test von _html_email (nicht via Alias)."""

    def _two_platform_listings(self):
        return [
            {**make_listing_dict(), "platform": "Kleinanzeigen", "listing_id": "ka-1"},
            {**make_listing_dict(), "platform": "Shpock", "listing_id": "shp-1"},
        ]

    def test_gibt_html_string_zurueck(self):
        html = _html_email(self._two_platform_listings())
        assert isinstance(html, str)
        assert "<html>" in html

    def test_digest_heading_wenn_is_digest_true(self):
        html = _html_email([make_listing_dict()], is_digest=True)
        assert "Tages-Digest" in html

    def test_alert_heading_wenn_is_digest_false(self):
        html = _html_email([make_listing_dict()], is_digest=False)
        assert "neue Babysachen" in html

    def test_beide_plattformen_enthalten(self):
        html = _html_email(self._two_platform_listings())
        assert "Kleinanzeigen" in html
        assert "Shpock" in html

    def test_skript_injection_in_titel_wird_escaped(self):
        listing = make_listing_dict(title='<script>alert(1)</script>')
        html = _html_email([listing])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestNormalizeServerUrl:

    def test_nur_ip_erhaelt_schema_und_port(self):
        assert _normalize_server_url("192.168.1.10") == "http://192.168.1.10:5000"

    def test_hostname_erhaelt_schema_und_port(self):
        assert _normalize_server_url("raspberrypi.local") == "http://raspberrypi.local:5000"

    def test_volle_url_bleibt_unveraendert(self):
        assert _normalize_server_url("http://192.168.1.10:5000") == "http://192.168.1.10:5000"

    def test_schema_vorhanden_port_fehlt(self):
        assert _normalize_server_url("http://192.168.1.10") == "http://192.168.1.10:5000"

    def test_eigener_port_bleibt_erhalten(self):
        assert _normalize_server_url("192.168.1.10:8080") == "http://192.168.1.10:8080"

    def test_https_wird_nicht_ueberschrieben(self):
        assert _normalize_server_url("https://myserver.example.com") == "https://myserver.example.com:5000"

    def test_trailing_slash_wird_entfernt(self):
        assert _normalize_server_url("http://192.168.1.10:5000/") == "http://192.168.1.10:5000"

    def test_leerstring_bleibt_leer(self):
        assert _normalize_server_url("") == ""


class TestCardHtmlDashboardLink:

    def test_dashboard_btn_vorhanden_wenn_db_id_und_server_url_gesetzt(self):
        html = _card_html("T", "P", "t", "10 €", "Ort", "https://x.com",
                          db_id=42, server_url="http://192.168.1.10:5000")
        assert "Im Dashboard" in html
        assert "/?modal=42" in html

    def test_kein_dashboard_btn_ohne_server_url(self):
        html = _card_html("T", "P", "t", "10 €", "Ort", "https://x.com",
                          db_id=42, server_url="")
        assert "Im Dashboard" not in html

    def test_kein_dashboard_btn_ohne_db_id(self):
        html = _card_html("T", "P", "t", "10 €", "Ort", "https://x.com",
                          db_id=None, server_url="http://192.168.1.10:5000")
        assert "Im Dashboard" not in html


# ── notify() ─────────────────────────────────────────────────

class TestNotify:

    _SETTINGS = {
        "email_enabled": "1",
        "email_subject_alert": "🔍 {n} neue Anzeige(n)",
        "email_sender": "test@example.com",
        "email_password": "secret",
        "email_recipient": "empfaenger@example.com",
    }

    def test_email_deaktiviert_gibt_false(self):
        result = notify([make_listing()], {**self._SETTINGS, "email_enabled": "0"})
        assert result is False

    def test_leere_listings_gibt_false(self):
        result = notify([], self._SETTINGS)
        assert result is False

    def test_sendet_und_markiert_notified(self):
        listing = make_listing(listing_id="nl-1")
        with patch("app.notifier._smtp_send", return_value=True) as mock_send, \
             patch("app.notifier.db.mark_listings_notified") as mock_mark, \
             patch("app.notifier.db.log_notification"):
            result = notify([listing], self._SETTINGS)
        assert result is True
        mock_send.assert_called_once()
        mock_mark.assert_called_once_with(["nl-1"])

    def test_kein_mark_bei_smtp_fehler(self):
        with patch("app.notifier._smtp_send", return_value=False), \
             patch("app.notifier.db.mark_listings_notified") as mock_mark:
            result = notify([make_listing()], self._SETTINGS)
        assert result is False
        mock_mark.assert_not_called()

    def test_betreff_platzhalter_wird_ersetzt(self):
        listing = make_listing()
        with patch("app.notifier._send_dicts") as mock_send:
            mock_send.return_value = False
            notify([listing, listing], self._SETTINGS)
        subject = mock_send.call_args[0][0]
        assert "2" in subject
        assert "{n}" not in subject


# ── send_digest() ─────────────────────────────────────────────

class TestSendDigest:

    _SETTINGS = {
        "email_enabled": "1",
        "digest_enabled": "1",
        "email_sender": "test@example.com",
        "email_password": "secret",
        "email_recipient": "empfaenger@example.com",
    }

    def test_digest_deaktiviert_gibt_false(self):
        result = send_digest({**self._SETTINGS, "digest_enabled": "0"})
        assert result is False

    def test_email_deaktiviert_gibt_false(self):
        result = send_digest({**self._SETTINGS, "email_enabled": "0"})
        assert result is False

    def test_keine_anzeigen_heute_gibt_false(self):
        with patch("app.notifier.db.get_listings_today", return_value=[]):
            result = send_digest(self._SETTINGS)
        assert result is False

    def test_sendet_digest_und_loggt(self):
        listing = make_listing_dict()
        with patch("app.notifier.db.get_listings_today", return_value=[listing]), \
             patch("app.notifier._smtp_send", return_value=True), \
             patch("app.notifier.db.log_notification") as mock_log:
            result = send_digest(self._SETTINGS)
        assert result is True
        mock_log.assert_called_once()
        call_args = mock_log.call_args[0]
        assert call_args[0] == "digest"

    def test_kein_log_bei_smtp_fehler(self):
        listing = make_listing_dict()
        with patch("app.notifier.db.get_listings_today", return_value=[listing]), \
             patch("app.notifier._smtp_send", return_value=False), \
             patch("app.notifier.db.log_notification") as mock_log:
            result = send_digest(self._SETTINGS)
        assert result is False
        mock_log.assert_not_called()

    def test_recipient_param_ueberspringt_enabled_checks(self):
        """send_digest(recipient=...) sendet auch wenn digest_enabled=0."""
        listing = make_listing_dict()
        settings_off = {**self._SETTINGS, "digest_enabled": "0", "email_enabled": "0"}
        with patch("app.notifier.db.get_listings_today", return_value=[listing]), \
             patch("app.notifier._smtp_send", return_value=True) as mock_smtp, \
             patch("app.notifier.db.log_notification"):
            result = send_digest(settings_off, recipient="profil@example.com")
        assert result is True
        mock_smtp.assert_called_once()

    def test_recipient_param_sendet_an_angegebene_adresse(self):
        listing = make_listing_dict()
        with patch("app.notifier.db.get_listings_today", return_value=[listing]), \
             patch("app.notifier._send_dicts") as mock_send, \
             patch("app.notifier.db.log_notification"):
            send_digest(self._SETTINGS, recipient="ziel@example.com")
        call_kwargs = mock_send.call_args
        recipients_arg = call_kwargs.kwargs.get("recipients") or (call_kwargs.args[3] if len(call_kwargs.args) > 3 else None)
        assert recipients_arg == ["ziel@example.com"]

    def test_recipient_keine_anzeigen_gibt_false(self):
        with patch("app.notifier.db.get_listings_today", return_value=[]):
            result = send_digest(self._SETTINGS, recipient="x@example.com")
        assert result is False
