"""Scraper für Willhaben.at via __NEXT_DATA__ JSON-Parsing."""

import json
import logging
import re
from typing import List, Optional
from urllib.parse import urlencode

import requests

from .base import BaseScraper, Listing, _float, _int, price_within_limit
from ..geo import haversine

logger = logging.getLogger(__name__)

BASE_URL = "https://www.willhaben.at"
SEARCH_URL = "https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9,de-DE;q=0.8",
}

_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)


def _attr(attributes: list, name: str) -> str:
    """Ersten Wert des genannten Attributs aus der Willhaben-Attributliste holen."""
    for attr in attributes:
        if attr.get("name") == name:
            values = attr.get("values", [])
            return values[0] if values else ""
    return ""


class WillhabenScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[float] = _float(settings.get("willhaben_max_price"))
        self.paylivery_only: bool = settings.get("willhaben_paylivery_only", "1") == "1"
        raw_radius = _int(settings.get("willhaben_radius", "50"))
        self.radius_km: int = 50 if raw_radius is None else raw_radius
        self._home: Optional[tuple] = self._resolve_home(settings)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    @staticmethod
    def _resolve_home(settings: dict) -> Optional[tuple]:
        lat = _float(settings.get("home_latitude"))
        lon = _float(settings.get("home_longitude"))
        if lat is not None and lon is not None:
            return (lat, lon)
        return None

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        logger.info(f"[Willhaben] '{term}'")
        results = []
        page = 1
        per_page = min(max_results, 30)

        while len(results) < max_results:
            params: dict = {
                "keyword": term,
                "rows": per_page,
                "page": page,
            }
            if self.paylivery_only:
                params["paylivery"] = "true"
            if self.max_price is not None:
                params["PRICE_TO"] = int(self.max_price)

            try:
                r = self.session.get(SEARCH_URL, params=params, timeout=15)
                r.raise_for_status()
            except Exception as e:
                logger.error(f"[Willhaben] Fehler bei '{term}': {e}")
                break

            adverts = self._extract_adverts(r.text)
            if not adverts:
                break

            for advert in adverts:
                if len(results) >= max_results:
                    break
                listing = self._parse(advert, term)
                if not listing:
                    continue
                if not price_within_limit(listing.price, self.max_price):
                    continue
                # Radius-Filter nur wenn PayLivery deaktiviert (sonst Versand → Distanz egal)
                if not self.paylivery_only and self._home and self.radius_km > 0:
                    coords = self._extract_coords(advert)
                    if coords and None not in coords:
                        dist = haversine(self._home[0], self._home[1], coords[0], coords[1])
                        if dist > self.radius_km:
                            continue
                results.append(listing)

            if len(adverts) < per_page:
                break
            page += 1

        logger.info(f"[Willhaben] {len(results)} Treffer für '{term}'.")
        return results

    def _extract_adverts(self, html: str) -> list:
        m = _NEXT_DATA_RE.search(html)
        if not m:
            logger.warning("[Willhaben] __NEXT_DATA__ nicht gefunden.")
            return []
        try:
            data = json.loads(m.group(1))
            return (
                data
                .get("props", {})
                .get("pageProps", {})
                .get("searchResult", {})
                .get("advertSummaryList", {})
                .get("advertSummary", [])
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"[Willhaben] JSON-Parse-Fehler: {e}")
            return []

    def _extract_coords(self, advert: dict) -> Optional[tuple]:
        attrs = advert.get("attributes", {}).get("attribute", [])
        raw = _attr(attrs, "COORDINATES")
        if raw and "," in raw:
            try:
                lat_s, lon_s = raw.split(",", 1)
                return (_float(lat_s.strip()), _float(lon_s.strip()))
            except Exception:
                pass
        return None

    def _parse(self, advert: dict, term: str) -> Optional[Listing]:
        try:
            advert_id = str(advert.get("id", ""))
            attrs = advert.get("attributes", {}).get("attribute", [])

            title = _attr(attrs, "HEADING") or "Unbekannt"
            price_raw = _attr(attrs, "PRICE_FOR_DISPLAY") or _attr(attrs, "PRICE") or "k.A."
            location = _attr(attrs, "LOCATION") or ""
            seo_url = _attr(attrs, "SEO_URL") or ""
            description = _attr(attrs, "BODY_DYN") or ""

            image_url = ""
            for attr in attrs:
                if attr.get("name") == "MMO":
                    vals = attr.get("values", [])
                    if vals:
                        image_url = vals[0]
                    break

            if seo_url.startswith("/"):
                url = f"{BASE_URL}{seo_url}"
            elif seo_url.startswith("http"):
                url = seo_url
            else:
                url = f"{BASE_URL}/iad/kaufen-und-verkaufen/d/{advert_id}"

            return Listing(
                platform="Willhaben",
                title=title,
                price=price_raw,
                location=location,
                url=url,
                listing_id=f"wh_{advert_id}",
                search_term=term,
                description=description,
                image_url=image_url,
            )
        except Exception as e:
            logger.debug(f"[Willhaben] Parse-Fehler: {e}")
            return None
