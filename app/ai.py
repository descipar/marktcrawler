"""KI-Integration: Verkäufer-Anfragetext und Preisvorschlag."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def _is_vb(price: str) -> bool:
    return bool(re.search(r"\bVB\b", price or "", re.IGNORECASE))


def _avg_price_for_term(price_stats: list, search_term: str) -> Optional[float]:
    """Mittlerer Preis aus price_stats für denselben Suchbegriff."""
    for s in price_stats or []:
        if s.get("search_term") == search_term and s.get("avg_price"):
            try:
                return float(s["avg_price"])
            except (TypeError, ValueError):
                pass
    return None


def generate_contact_text(listing: dict, price_stats: list, settings: dict) -> str:
    """Generiert einen Verkäufer-Anfragetext via KI-API.

    Unterstützt Anthropic Claude, OpenAI und Ollama (OpenAI-kompatibel via base_url).
    Gibt bei Fehler eine lesbare Fehlermeldung zurück (kein raise).
    """
    api_key = settings.get("ai_api_key", "").strip()
    model = settings.get("ai_model", "claude-haiku-4-5-20251001").strip()
    base_url = settings.get("ai_base_url", "").strip()
    provider = _detect_provider(model, base_url)

    if not api_key and provider != "ollama":
        return "⚠️ Kein API-Key hinterlegt. Bitte in den Einstellungen unter KI-Assistent eintragen."

    title = listing.get("title", "")
    price = listing.get("price", "")
    location = listing.get("location", "")
    platform = listing.get("platform", "")
    search_term = listing.get("search_term", "")
    description = (listing.get("description") or "")[:500]

    vb = _is_vb(price)
    avg = _avg_price_for_term(price_stats, search_term) if vb else None

    price_hint = ""
    if vb and avg:
        suggested = round(avg * 0.85 / 5) * 5  # 15% unter Schnitt, auf 5 € gerundet
        price_hint = (
            f"\nDer Artikel ist als VB ausgezeichnet. Laut meinen gesammelten Daten liegt der "
            f"Durchschnittspreis für '{search_term}' bei ca. {avg:.0f} €. "
            f"Schlage einen Preis von {suggested} € vor, falls es zur Anzeige passt."
        )

    prompt = f"""Schreib eine kurze, freundliche Kaufanfrage auf Deutsch für folgende Kleinanzeige.

Artikel: {title}
Preis: {price}
Ort: {location}
Plattform: {platform}
{"Beschreibung: " + description if description else ""}
{price_hint}

Anforderungen:
- Maximal 4–5 Sätze
- Höflich und natürlich, keine übertriebene Förmlichkeit
- Interesse am Artikel bekunden
- Nach Verfügbarkeit / Besichtigung fragen{" und einen Preisvorschlag machen" if vb else ""}
- Keinen Namen unterschreiben (wird manuell ergänzt)
- Nur den Text, keine Erklärungen drum herum"""

    try:
        if provider == "anthropic":
            return _call_anthropic(api_key, model, prompt)
        elif provider in ("openai", "ollama"):
            return _call_openai_compat(api_key, model, prompt, base_url)
        else:
            return f"⚠️ Unbekannter Provider für Modell '{model}'. Unterstützt: claude-*, gpt-*, oder Ollama via Base-URL."
    except Exception as e:
        logger.error(f"[KI] Fehler bei Textgenerierung: {e}")
        return f"⚠️ Fehler bei der Textgenerierung: {e}"


def _detect_provider(model: str, base_url: str = "") -> str:
    if base_url:
        return "ollama"
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gpt-", "o1", "o3")):
        return "openai"
    return "unknown"


def _call_anthropic(api_key: str, model: str, prompt: str) -> str:
    try:
        import anthropic
    except ImportError:
        return "⚠️ Paket 'anthropic' nicht installiert. Bitte: pip install anthropic"

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _call_openai_compat(api_key: str, model: str, prompt: str, base_url: str = "") -> str:
    """OpenAI-kompatibler Call – funktioniert für OpenAI und Ollama."""
    try:
        import openai
    except ImportError:
        return "⚠️ Paket 'openai' nicht installiert. Bitte: pip install openai"

    kwargs = {"api_key": api_key or "ollama"}
    if base_url:
        kwargs["base_url"] = base_url
    client = openai.OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


# Alias für Rückwärtskompatibilität mit Tests
def _call_openai(api_key: str, model: str, prompt: str) -> str:
    return _call_openai_compat(api_key, model, prompt)
