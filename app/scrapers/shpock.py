"""Scraper für Shpock via GraphQL-API."""

import logging
from typing import List, Optional
import requests
from .base import Listing

logger = logging.getLogger(__name__)

API_URL = "https://www.shpock.com/graphql"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Content-Type": "application/json",
    "x-shpock-device-id": "baby-crawler",
}
QUERY = """
query Search($q:String!,$lat:Float,$lon:Float,$radius:Int,$maxPrice:Int,$limit:Int){
  itemSearch(query:$q,location:{latitude:$lat,longitude:$lon,radius:$radius},
             price:{max:$maxPrice},limit:$limit){
    items{id title description price media{images{url}}
          location{city country} path}}}
"""


class ShpockScraper:
    def __init__(self, settings: dict):
        self.max_price: Optional[int] = _int(settings.get("shpock_max_price"))
        self.lat: float = float(settings.get("shpock_latitude") or 51.5136)
        self.lon: float = float(settings.get("shpock_longitude") or 7.4653)
        self.radius_km: int = _int(settings.get("shpock_radius", 30)) or 30
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        logger.info(f"[Shpock] '{term}'")
        variables = {
            "q": term, "lat": self.lat, "lon": self.lon,
            "radius": self.radius_km * 1000, "limit": max_results,
        }
        if self.max_price:
            variables["maxPrice"] = self.max_price * 100
        try:
            r = self.session.post(API_URL, json={"query": QUERY, "variables": variables}, timeout=15)
            r.raise_for_status()
            items = r.json().get("data", {}).get("itemSearch", {}).get("items", [])
        except Exception as e:
            logger.error(f"[Shpock] Fehler bei '{term}': {e}")
            return []

        results = [x for x in (self._parse(i, term) for i in items) if x]
        logger.info(f"[Shpock] {len(results)} Treffer für '{term}'.")
        return results

    def _parse(self, item: dict, term: str) -> Optional[Listing]:
        try:
            raw_price = item.get("price", 0)
            price_str = (f"{raw_price/100:.2f} €" if isinstance(raw_price, (int, float)) and raw_price > 500
                         else (f"{raw_price} €" if raw_price else "k.A."))
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


def _int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
