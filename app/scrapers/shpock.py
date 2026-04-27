"""Scraper für Shpock via GraphQL-API."""

import json
import logging
from typing import List, Optional
import requests
from .base import BaseScraper, Listing, _int
from ..geo import geocode, haversine

logger = logging.getLogger(__name__)

API_URL = "https://www.shpock.com/graphql"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Content-Type": "application/json",
}

ITEM_SEARCH_QUERY = """
query ItemSearch($serializedFilters: String, $pagination: Pagination, $trackingSource: TrackingSource!) {
  itemSearch(
    serializedFilters: $serializedFilters
    pagination: $pagination
    trackingSource: $trackingSource
  ) {
    od
    offset
    limit
    count
    total
    itemResults {
      items {
        __typename
        ... on ItemSummary {
          id
          title
          description
          price
          currency
          locality
          distance
          distanceUnit
          path
          isSold
          isFree
          media { id }
        }
      }
    }
  }
}
"""


class ShpockScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[int] = _int(settings.get("shpock_max_price"))
        raw = _int(settings.get("shpock_radius", "30"))
        self.radius_km: int = 30 if raw is None else raw
        self.lat = float(settings.get("shpock_latitude") or 51.5136)
        self.lon = float(settings.get("shpock_longitude") or 7.4653)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        filters = {
            "q": term,
            "distance": {
                "lat": self.lat,
                "lng": self.lon,
                "radius": self.radius_km * 1000,
            },
        }
        if self.max_price:
            filters["price"] = {"max": self.max_price}

        payload = {
            "query": ITEM_SEARCH_QUERY,
            "variables": {
                "serializedFilters": json.dumps(filters),
                "pagination": {"limit": max_results * 3, "offset": 0},
                "trackingSource": "Search",
            },
        }

        try:
            resp = self.session.post(API_URL, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[Shpock] API-Fehler: {e}")
            return []

        errors = data.get("errors")
        if errors:
            logger.error(f"[Shpock] GraphQL-Fehler: {errors}")
            return []

        item_results = (
            data.get("data", {})
            .get("itemSearch", {})
            .get("itemResults", [])
        )

        results: List[Listing] = []
        for group in item_results:
            for item in group.get("items", []):
                if item.get("__typename") != "ItemSummary":
                    continue
                if item.get("isSold"):
                    continue
                if self.radius_km > 0:
                    locality = item.get("locality", "")
                    if locality:
                        coords = geocode(locality)
                        if coords:
                            dist_km = haversine(self.lat, self.lon, coords[0], coords[1])
                            if dist_km > self.radius_km:
                                continue
                listing = self._parse(item, term)
                if listing is None:
                    continue
                if self.max_price and listing.price != "k.A.":
                    try:
                        price_val = float(listing.price.replace("€", "").replace(",", ".").strip())
                        if price_val > self.max_price:
                            continue
                    except ValueError:
                        pass
                results.append(listing)
                if len(results) >= max_results:
                    return results

        if not results and self.radius_km > 0:
            logger.warning(
                f"[Shpock] '{term}': API hat Ergebnisse geliefert, aber keine liegt im "
                f"{self.radius_km}-km-Radius um ({self.lat}, {self.lon}). "
                "Shpock ignoriert den Standortfilter ohne Session – ggf. Radius erhöhen."
            )
        return results

    def _parse(self, item: dict, term: str) -> Optional[Listing]:
        try:
            raw_price = item.get("price")
            if item.get("isFree") or raw_price == 0:
                price_str = "0 €"
            elif isinstance(raw_price, (int, float)) and raw_price > 0:
                price_str = f"{raw_price:.2f} €"
            else:
                price_str = "k.A."

            media = item.get("media") or []
            image_url = f"https://m1.secondhandapp.at/full/{media[0]['id']}" if media else ""
            path = item.get("path", "")

            return Listing(
                platform="Shpock",
                title=item.get("title", "Unbekannt"),
                price=price_str,
                location=item.get("locality", ""),
                url=f"https://www.shpock.com{path}" if path else "https://www.shpock.com",
                listing_id=f"sp_{item.get('id', '')}",
                search_term=term,
                description=item.get("description", ""),
                image_url=image_url,
            )
        except Exception as e:
            logger.debug(f"[Shpock] Parse-Fehler: {e}")
            return None
