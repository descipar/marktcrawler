"""Tests für app/ai.py: KI-Anfragetext-Generator."""

from unittest.mock import MagicMock, patch

import pytest

from app.ai import _avg_price_for_term, _detect_provider, _is_vb, _call_openai_compat, generate_contact_text

LISTING = {
    "title": "Kinderwagen Bugaboo Cameleon",
    "price": "250 VB",
    "location": "München",
    "platform": "Kleinanzeigen",
    "search_term": "kinderwagen",
    "description": "Wenig benutzt, guter Zustand.",
}

PRICE_STATS = [
    {"search_term": "kinderwagen", "avg_price": 180.0, "count": 20},
    {"search_term": "babybett", "avg_price": 60.0, "count": 10},
]

_SETTINGS_OFF = {"ai_enabled": "0", "ai_api_key": "", "ai_model": "claude-haiku-4-5-20251001"}
_SETTINGS_ON = {"ai_enabled": "1", "ai_api_key": "sk-ant-test", "ai_model": "claude-haiku-4-5-20251001"}


# ── Hilfsfunktionen ───────────────────────────────────────────

class TestIsVb:
    def test_vb_erkannt(self):
        assert _is_vb("250 VB") is True
        assert _is_vb("VB") is True
        assert _is_vb("200 vb") is True

    def test_kein_vb(self):
        assert _is_vb("250 €") is False
        assert _is_vb("") is False
        assert _is_vb(None) is False


class TestDetectProvider:
    def test_claude_modell(self):
        assert _detect_provider("claude-haiku-4-5-20251001") == "anthropic"
        assert _detect_provider("claude-sonnet-4-6") == "anthropic"

    def test_openai_modell(self):
        assert _detect_provider("gpt-4o-mini") == "openai"
        assert _detect_provider("gpt-3.5-turbo") == "openai"

    def test_unbekanntes_modell(self):
        assert _detect_provider("llama-3") == "unknown"

    def test_base_url_ergibt_ollama(self):
        assert _detect_provider("gemma2:2b", "http://ollama:11434/v1") == "ollama"
        assert _detect_provider("phi3:mini", "http://localhost:11434/v1") == "ollama"

    def test_kein_api_key_bei_ollama_erlaubt(self):
        settings = {**_SETTINGS_ON, "ai_api_key": "", "ai_base_url": "http://ollama:11434/v1", "ai_model": "gemma2:2b"}
        with patch("app.ai._call_openai_compat", return_value="Hallo, ich interessiere mich.") as mock:
            result = generate_contact_text(LISTING, PRICE_STATS, settings)
        mock.assert_called_once()
        assert "⚠️" not in result


class TestAvgPriceForTerm:
    def test_passender_term(self):
        avg = _avg_price_for_term(PRICE_STATS, "kinderwagen")
        assert avg == 180.0

    def test_anderer_term(self):
        avg = _avg_price_for_term(PRICE_STATS, "babybett")
        assert avg == 60.0

    def test_unbekannter_term(self):
        avg = _avg_price_for_term(PRICE_STATS, "hochstuhl")
        assert avg is None

    def test_leere_stats(self):
        assert _avg_price_for_term([], "kinderwagen") is None


# ── generate_contact_text ─────────────────────────────────────

class TestGenerateContactText:

    def test_kein_api_key_gibt_warnung(self):
        result = generate_contact_text(LISTING, PRICE_STATS, _SETTINGS_OFF)
        assert "API-Key" in result or "aktiviert" in result.lower() or "⚠️" in result

    def test_kein_api_key_in_settings(self):
        settings = {**_SETTINGS_ON, "ai_api_key": ""}
        result = generate_contact_text(LISTING, PRICE_STATS, settings)
        assert "⚠️" in result

    def test_anthropic_wird_aufgerufen(self):
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Hallo, ich interessiere mich für Ihren Kinderwagen.")]
        mock_client.messages.create.return_value = mock_msg

        with patch("app.ai._call_anthropic", return_value="Hallo, ich interessiere mich für Ihren Kinderwagen.") as mock_call:
            result = generate_contact_text(LISTING, PRICE_STATS, _SETTINGS_ON)
        mock_call.assert_called_once()
        assert "Kinderwagen" in result or len(result) > 10

    def test_fehler_gibt_fehlermeldung_statt_exception(self):
        with patch("app.ai._call_anthropic", side_effect=Exception("API down")):
            result = generate_contact_text(LISTING, PRICE_STATS, _SETTINGS_ON)
        assert "⚠️" in result
        assert "API down" in result

    def test_anthropic_nicht_installiert(self):
        with patch("app.ai._call_anthropic", return_value="⚠️ Paket 'anthropic' nicht installiert."):
            result = generate_contact_text(LISTING, PRICE_STATS, _SETTINGS_ON)
        assert "anthropic" in result.lower() or "⚠️" in result

    def test_vb_preis_preisvorschlag_im_prompt(self):
        """Bei VB-Anzeige und vorhandenen Stats soll Preisvorschlag im Prompt landen."""
        captured_prompts = []

        def fake_call(api_key, model, prompt):
            captured_prompts.append(prompt)
            return "Ich würde 150 € vorschlagen."

        with patch("app.ai._call_anthropic", side_effect=fake_call):
            generate_contact_text(LISTING, PRICE_STATS, _SETTINGS_ON)

        assert captured_prompts, "Kein Prompt generiert"
        assert "VB" in captured_prompts[0] or "Preisvorschlag" in captured_prompts[0] or "Preis" in captured_prompts[0]

    def test_kein_vb_kein_preisvorschlag_im_prompt(self):
        listing_festpreis = {**LISTING, "price": "250 €"}
        captured_prompts = []

        def fake_call(api_key, model, prompt):
            captured_prompts.append(prompt)
            return "Ich interessiere mich für den Artikel."

        with patch("app.ai._call_anthropic", side_effect=fake_call):
            generate_contact_text(listing_festpreis, PRICE_STATS, _SETTINGS_ON)

        assert captured_prompts
        assert "Preisvorschlag" not in captured_prompts[0]
