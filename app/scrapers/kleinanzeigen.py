"""Scraper für Kleinanzeigen.de (requests + BeautifulSoup).

Die korrekte URL für ortsbasierte Suche lautet:
  /s-{city-slug}/{keyword}/k0l{locationId}r{radius}?maxPrice=N
Die locationId wird einmalig pro Crawl-Lauf via Formular-Submit ermittelt.
"""

import logging
import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing, _int, price_within_limit, _large_image_url

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kleinanzeigen.de"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
}


class KleinanzeigenScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[int] = _int(settings.get("kleinanzeigen_max_price"))
        self.location: str = settings.get("kleinanzeigen_location", "")
        self.radius_km: int = _int(settings.get("kleinanzeigen_radius", 30)) or 30
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # Einmalig beim Start: locationId via Formular-Submit ermitteln
        self._location_id: Optional[int] = self._resolve_location_id()

    def _resolve_location_id(self) -> Optional[int]:
        """Ermittelt Kleinanzeigen-interne locationId für den konfigurierten Ort.

        Kleinanzeigen verwendet interne IDs statt Orts-Slugs für echte
        Umkreissuche. Diese werden über einen Formular-Submit abgefragt,
        der die korrekte URL mit l{id}r{radius} zurückliefert.
        """
        if not self.location:
            return None
        try:
            r = self.session.get(
                f"{BASE_URL}/s-suchanfrage.html",
                params={
                    "categoryId": "", "locationId": "",
                    "keywords": "test", "locationStr": self.location,
                    "radius": str(self.radius_km),
                },
                timeout=15, allow_redirects=True,
            )
            m = re.search(r"/k0l(\d+)r", r.url)
            if m:
                lid = int(m.group(1))
                logger.info(f"[Kleinanzeigen] locationId für '{self.location}': {lid}")
                return lid
            logger.warning(f"[Kleinanzeigen] locationId für '{self.location}' nicht gefunden (URL: {r.url})")
        except Exception as e:
            logger.warning(f"[Kleinanzeigen] locationId-Lookup fehlgeschlagen: {e}")
        return None

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        url = self._build_url(term)
        logger.info(f"[Kleinanzeigen] '{term}' → {url}")
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[Kleinanzeigen] Fehler bei '{term}': {e}")
            return []

        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select("article.aditem") or soup.select("li[data-adid]")
        results = []
        for item in items[:max_results]:
            listing = self._parse(item, term)
            if listing and self._price_ok(listing):
                results.append(listing)
        logger.info(f"[Kleinanzeigen] {len(results)} Treffer für '{term}'.")
        return results

    def _build_url(self, term: str) -> str:
        # Keyword als URL-Slug (Leerzeichen → Bindestrich, Umlaute → ASCII)
        keyword = _ascii_slug(term.strip())

        if self.location and self._location_id:
            # Korrekte Umkreissuche mit locationId
            city_slug = _ascii_slug(self.location)
            url = (
                f"{BASE_URL}/s-{city_slug}/{keyword}"
                f"/k0l{self._location_id}r{self.radius_km}"
            )
            if self.max_price:
                url += f"?maxPrice={self.max_price}"
        else:
            # Fallback: bundesweite Suche (wenn kein Ort konfiguriert)
            keyword_q = term.strip().replace(" ", "+")
            url = f"{BASE_URL}/s-anzeigen/q-{keyword_q}/k0"
            params = []
            if self.max_price:
                params.append(f"maxPrice={self.max_price}")
            if self.radius_km:
                params.append(f"radius={self.radius_km}")
            url += ("?" + "&".join(params) if params else "")
        return url

    def _parse(self, item, term: str) -> Optional[Listing]:
        try:
            title_el = (
                item.select_one("h2.text-module-begin a")
                or item.select_one("a.ellipsis")
                or item.select_one("[data-testid='aditem-title']")
            )
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not href.startswith("http"):
                href = BASE_URL + href
            m = re.search(r"/(\d+)(?:-[^/]+)?$", href)
            lid = m.group(1) if m else href[-20:]

            price_el = (
                item.select_one("p.aditem-main--middle--price-shipping--price")
                or item.select_one("[data-testid='aditem-price']")
            )
            price = price_el.get_text(strip=True) if price_el else "k.A."

            loc_el = item.select_one("div.aditem-main--top--left") or item.select_one(".aditem-addon")
            location = " ".join(loc_el.get_text().split()) if loc_el else ""

            desc_el = item.select_one("p.aditem-main--middle--description")
            description = desc_el.get_text(strip=True) if desc_el else ""

            img_el = (
                item.select_one("img.aditem-image")
                or item.select_one("img[data-imgsrc]")
                or item.select_one(".aditem-image img")
                or item.select_one("img[src*='img.kleinanzeigen']")
                or item.select_one("img[src*='i.ebayimg']")
                or item.select_one("img")
            )
            image_url = ""
            if img_el:
                image_url = (img_el.get("src") or img_el.get("data-src")
                             or img_el.get("data-imgsrc") or "")

            return Listing(
                platform="Kleinanzeigen",
                title=title, price=price, location=location,
                url=href, listing_id=f"ka_{lid}",
                search_term=term, description=description,
                image_url=image_url, image_url_large=_large_image_url(image_url),
            )
        except Exception as e:
            logger.debug(f"[Kleinanzeigen] Parse-Fehler: {e}")
            return None

    def _price_ok(self, l: Listing) -> bool:
        return price_within_limit(l.price, self.max_price)


def _ascii_slug(text: str) -> str:
    """Konvertiert Text in Kleinanzeigen-URL-Slug (Umlaute → ASCII, Leerzeichen → Bindestrich)."""
    slug = text.lower()
    for umlaut, ascii_ in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        slug = slug.replace(umlaut, ascii_)
    slug = re.sub(r"\s+", "-", slug)
    return slug
