"""Scraper für markt.de (requests + BeautifulSoup)."""

import logging
import re
from typing import List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing, _float, _int, price_within_limit

logger = logging.getLogger(__name__)

BASE_URL = "https://www.markt.de"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                          "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def _city_slug(city: str) -> str:
    return city.strip().lower().translate(_UMLAUT).replace(" ", "-")


class MarktdeScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[float] = _float(settings.get("marktde_max_price"))
        self.location: str = settings.get("marktde_location", "").strip()
        self.radius_km: int = _int(settings.get("marktde_radius", "50")) or 50
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        city_slug = _city_slug(self.location) if self.location else "deutschland"
        term_slug = quote(term.strip(), safe="")
        logger.info(f"[markt.de] '{term}' in '{self.location}'")

        results = []
        page = 1

        while len(results) < max_results:
            url = f"{BASE_URL}/{city_slug}/suche/{term_slug}/"
            params: dict = {"radius": self.radius_km}
            if page > 1:
                params["page"] = page
            try:
                r = self.session.get(url, params=params, timeout=15)
                r.raise_for_status()
            except Exception as e:
                logger.error(f"[markt.de] Fehler bei '{term}': {e}")
                break

            soup = BeautifulSoup(r.text, "lxml")
            items = soup.select(".clsy-c-result-list-item")
            if not items:
                break

            for item in items:
                if len(results) >= max_results:
                    break
                listing = self._parse(item, term)
                if listing and price_within_limit(listing.price, self.max_price):
                    results.append(listing)

            if len(items) < 20:
                break
            page += 1

        logger.info(f"[markt.de] {len(results)} Treffer für '{term}'.")
        return results

    def _parse(self, item, term: str) -> Optional[Listing]:
        try:
            link_el = item.select_one(".clsy-c-result-list-item__link")
            if not link_el:
                return None
            title = link_el.get_text(strip=True)
            if not title:
                return None
            href = link_el.get("href", "")
            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            m = re.search(r"/(\d+)(?:/|\?|$)", href)
            lid = m.group(1) if m else re.sub(r"[^a-z0-9]", "_", href[-24:])

            price_el = item.select_one(".clsy-c-result-list-item__price-amount")
            price = price_el.get_text(strip=True) if price_el else "k.A."

            loc_el = item.select_one(".clsy-c-result-list-item__location")
            location = loc_el.get_text(strip=True) if loc_el else ""

            img_el = item.select_one(".clsy-c-result-list-item__thumbnail img")
            image_url = ""
            if img_el:
                image_url = (
                    img_el.get("src")
                    or img_el.get("data-src")
                    or img_el.get("data-lazy-src")
                    or ""
                )

            desc_el = item.select_one(".clsy-c-result-list-item__description")
            description = desc_el.get_text(strip=True) if desc_el else ""

            return Listing(
                platform="markt.de",
                title=title,
                price=price,
                location=location,
                url=url,
                listing_id=f"md_{lid}",
                search_term=term,
                description=description,
                image_url=image_url,
            )
        except Exception as e:
            logger.debug(f"[markt.de] Parse-Fehler: {e}")
            return None
