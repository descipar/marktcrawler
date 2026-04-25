"""Scraper für Vinted via öffentliche API."""

import logging
from typing import List, Optional

import requests

from .base import Listing, _float, _int
from ..geo import geocode, haversine

logger = logging.getLogger(__name__)

API_URL = "https://www.vinted.de/api/v2/catalog/items"
BASE_URL = "https://www.vinted.de"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9",
    "Referer": "https://www.vinted.de/",
}


class VintedScraper:
    def __init__(self, settings: dict):
        self.max_price: Optional[float] = _float(settings.get("vinted_max_price"))
        raw = _int(settings.get("vinted_radius", "30"))
        self.radius_km: int = 30 if raw is None else raw
        self._home: Optional[tuple] = self._resolve_location(settings)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._authenticate()

    @staticmethod
    def _resolve_location(settings: dict) -> Optional[tuple]:
        city = settings.get("vinted_location", "").strip()
        if city:
            coords = geocode(city)
            if coords:
                return coords
            logger.warning(f"[Vinted] Stadtname '{city}' konnte nicht geocodiert werden.")
        return None

    def _authenticate(self) -> None:
        """Holt anonym ausgestellte JWT-Cookies (access_token_web) von der Startseite."""
        try:
            self.session.get(BASE_URL, timeout=15)
        except Exception as e:
            logger.warning(f"[Vinted] Authentifizierung fehlgeschlagen: {e}")

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        logger.info(f"[Vinted] '{term}'")
        params: dict = {
            "search_text": term,
            "per_page": max_results,
            "order": "newest_first",
        }
        if self.max_price is not None:
            params["price_to"] = self.max_price
        try:
            r = self.session.get(API_URL, params=params, timeout=15)
            if r.status_code == 401:
                logger.info("[Vinted] 401 – hole neuen Session-Cookie...")
                self._authenticate()
                r = self.session.get(API_URL, params=params, timeout=15)
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:
            logger.error(f"[Vinted] Fehler bei '{term}': {e}")
            return []

        results = []
        for item in items:
            listing = self._parse(item, term)
            if not listing:
                continue
            if self._home and self.radius_km > 0:
                city = (item.get("user") or {}).get("city", "")
                if city:
                    coords = geocode(city)
                    if coords and haversine(self._home[0], self._home[1], coords[0], coords[1]) > self.radius_km:
                        continue
            results.append(listing)
        logger.info(f"[Vinted] {len(results)} Treffer für '{term}'.")
        return results

    def _parse(self, item: dict, term: str) -> Optional[Listing]:
        try:
            item_id = str(item.get("id", ""))

            raw_price = item.get("price")
            if isinstance(raw_price, dict):
                raw_price = raw_price.get("amount")
            if raw_price is None:
                raw_price = (item.get("total_item_price") or {}).get("amount")
            try:
                price_str = f"{float(raw_price):.2f} €" if raw_price not in (None, "") else "k.A."
            except (ValueError, TypeError):
                price_str = "k.A."

            user = item.get("user") or {}
            location = user.get("city", "")

            photo = item.get("photo") or {}
            image_url = photo.get("url", "")

            return Listing(
                platform="Vinted",
                title=item.get("title", "Unbekannt"),
                price=price_str,
                location=location,
                url=item.get("url", f"https://www.vinted.de/items/{item_id}"),
                listing_id=f"vt_{item_id}",
                search_term=term,
                description=item.get("description", ""),
                image_url=image_url,
            )
        except Exception as e:
            logger.debug(f"[Vinted] Parse-Fehler: {e}")
            return None


