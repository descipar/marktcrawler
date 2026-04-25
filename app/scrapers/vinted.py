"""Scraper für Vinted via öffentliche API."""

import logging
from typing import List, Optional

import requests

from .base import Listing, _float

logger = logging.getLogger(__name__)

API_URL = "https://www.vinted.de/api/v2/catalog/items"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9",
}


class VintedScraper:
    def __init__(self, settings: dict):
        self.max_price: Optional[float] = _float(settings.get("vinted_max_price"))
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

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
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:
            logger.error(f"[Vinted] Fehler bei '{term}': {e}")
            return []

        results = [x for x in (self._parse(i, term) for i in items) if x]
        logger.info(f"[Vinted] {len(results)} Treffer für '{term}'.")
        return results

    def _parse(self, item: dict, term: str) -> Optional[Listing]:
        try:
            item_id = str(item.get("id", ""))

            raw_price = item.get("price")
            if raw_price is None:
                raw_price = (item.get("total_item_price") or {}).get("amount")
            price_str = f"{raw_price} €" if raw_price not in (None, "") else "k.A."

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


