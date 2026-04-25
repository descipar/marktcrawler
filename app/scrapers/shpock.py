"""Scraper für Shpock via GraphQL-API.

HINWEIS: Die Shpock GraphQL-API wurde umgebaut. Die alten Felder
(query, location, price, items) existieren nicht mehr. Der Scraper
gibt daher aktuell keine Ergebnisse zurück und ist deaktiviert.
"""

import logging
from typing import List, Optional
import requests
from .base import Listing, _int
from ..geo import geocode

logger = logging.getLogger(__name__)

API_URL = "https://www.shpock.com/graphql"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Content-Type": "application/json",
    "x-shpock-device-id": "baby-crawler",
}

_API_WARNING_SHOWN = False


class ShpockScraper:
    def __init__(self, settings: dict):
        self.max_price: Optional[int] = _int(settings.get("shpock_max_price"))
        self.radius_km: int = _int(settings.get("shpock_radius", 30)) or 30
        self.lat, self.lon = self._resolve_location(settings)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    @staticmethod
    def _resolve_location(settings: dict):
        """Gibt (lat, lon) zurück – per Geocoding aus Stadtname oder direkt aus Koordinaten."""
        city = settings.get("shpock_location", "").strip()
        if city:
            coords = geocode(city)
            if coords:
                return coords
            logger.warning(f"[Shpock] Stadtname '{city}' konnte nicht geocodiert werden – Fallback auf Koordinaten.")
        lat = float(settings.get("shpock_latitude") or 51.5136)
        lon = float(settings.get("shpock_longitude") or 7.4653)
        return lat, lon

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        global _API_WARNING_SHOWN
        if not _API_WARNING_SHOWN:
            logger.warning(
                "[Shpock] API nicht verfügbar: Die Shpock GraphQL-API wurde umgebaut "
                "und unterstützt keine Keyword-Suche mehr. Shpock liefert keine Ergebnisse. "
                "Bitte deaktiviere Shpock in den Einstellungen."
            )
            _API_WARNING_SHOWN = True
        return []

    def _parse(self, item: dict, term: str) -> Optional[Listing]:
        try:
            raw_price = item.get("price", 0)
            # Shpock liefert Preise in Cent (integer) → immer durch 100 teilen
            if isinstance(raw_price, (int, float)) and raw_price > 0:
                price_str = f"{raw_price / 100:.2f} €"
            else:
                price_str = "k.A."
            loc = item.get("location") or {}
            location = ", ".join(filter(None, [loc.get("city"), loc.get("country")]))
            path = item.get("path", "")
            images = (item.get("media") or {}).get("images", [])
            return Listing(
                platform="Shpock",
                title=item.get("title", "Unbekannt"),
                price=price_str, location=location,
                url=f"https://www.shpock.com{path}" if path else "https://www.shpock.com",
                listing_id=f"sp_{item.get('id', '')}",
                search_term=term,
                description=item.get("description", ""),
                image_url=images[0].get("url", "") if images else "",
            )
        except Exception as e:
            logger.debug(f"[Shpock] Parse-Fehler: {e}")
            return None


