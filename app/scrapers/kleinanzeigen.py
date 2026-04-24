"""Scraper für Kleinanzeigen.de (requests + BeautifulSoup)."""

import logging
import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .base import Listing

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


class KleinanzeigenScraper:
    def __init__(self, settings: dict):
        self.max_price: Optional[int] = _int(settings.get("kleinanzeigen_max_price"))
        self.location: str = settings.get("kleinanzeigen_location", "")
        self.radius_km: int = _int(settings.get("kleinanzeigen_radius", 30)) or 30
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

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
        # Keyword-Suche mit q- Prefix – funktioniert für einzelne Wörter
        # UND für mehrteilige Beschreibungen wie "babyschale rot maxi-cosi"
        keyword = term.strip().replace(" ", "+")
        params = []
        if self.max_price:
            params.append(f"maxPrice={self.max_price}")
        if self.radius_km:
            params.append(f"radius={self.radius_km}")
        if self.location:
            loc = self.location.replace(" ", "-").lower()
            url = f"{BASE_URL}/s-{loc}/q-{keyword}/k0"
        else:
            url = f"{BASE_URL}/s-anzeigen/q-{keyword}/k0"
        return url + ("?" + "&".join(params) if params else "")

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
            location = loc_el.get_text(strip=True) if loc_el else ""

            desc_el = item.select_one("p.aditem-main--middle--description")
            description = desc_el.get_text(strip=True) if desc_el else ""

            img_el = item.select_one("img.aditem-image")
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            return Listing(
                platform="Kleinanzeigen",
                title=title, price=price, location=location,
                url=href, listing_id=f"ka_{lid}",
                search_term=term, description=description, image_url=image_url,
            )
        except Exception as e:
            logger.debug(f"[Kleinanzeigen] Parse-Fehler: {e}")
            return None

    def _price_ok(self, l: Listing) -> bool:
        if not self.max_price:
            return True
        m = re.search(r"(\d[\d.]*)", l.price.replace(".", "").replace(",", "."))
        if m:
            try:
                return float(m.group(1)) <= self.max_price
            except ValueError:
                pass
        return True


def _int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
