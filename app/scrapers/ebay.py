"""Scraper für eBay.de (requests + BeautifulSoup)."""

import logging
import re
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .base import Listing

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ebay.de"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
}


class EbayScraper:
    def __init__(self, settings: dict):
        self.max_price: Optional[float] = _float(settings.get("ebay_max_price"))
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        url = self._build_url(term, max_results)
        logger.info(f"[eBay] '{term}' → {url}")
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
        except Exception as e:
            logger.error(f"[eBay] Fehler bei '{term}': {e}")
            return []

        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select("li.s-item:not(.s-item--placeholder)")
        results = []
        for item in items[:max_results]:
            listing = self._parse(item, term)
            if listing and self._price_ok(listing):
                results.append(listing)
        logger.info(f"[eBay] {len(results)} Treffer für '{term}'.")
        return results

    def _build_url(self, term: str, max_results: int) -> str:
        keyword = term.strip().replace(" ", "+")
        # _sop=10: nach Neuheit sortieren; _ipg: Ergebnisse pro Seite
        return f"{BASE_URL}/sch/i.html?_nkw={keyword}&_sop=10&_ipg={min(max_results, 50)}"

    def _parse(self, item, term: str) -> Optional[Listing]:
        try:
            title_el = item.select_one(".s-item__title")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            if title.lower() == "shop on ebay":
                return None

            link_el = item.select_one("a.s-item__link")
            url = link_el.get("href", "") if link_el else ""
            m = re.search(r"/itm/(\d+)", url)
            lid = m.group(1) if m else url[-20:]

            price_el = item.select_one(".s-item__price")
            price = price_el.get_text(strip=True) if price_el else "k.A."

            loc_el = (
                item.select_one(".s-item__location")
                or item.select_one(".s-item__itemLocation")
            )
            location = loc_el.get_text(strip=True).replace("Standort:\xa0", "").replace("Standort: ", "") if loc_el else ""

            img_el = item.select_one(".s-item__image-img")
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            return Listing(
                platform="eBay",
                title=title,
                price=price,
                location=location,
                url=url,
                listing_id=f"eb_{lid}",
                search_term=term,
                image_url=image_url,
            )
        except Exception as e:
            logger.debug(f"[eBay] Parse-Fehler: {e}")
            return None

    def _price_ok(self, listing: Listing) -> bool:
        if not self.max_price:
            return True
        m = re.search(r"(\d[\d.]*)", listing.price.replace(".", "").replace(",", "."))
        if m:
            try:
                return float(m.group(1)) <= self.max_price
            except ValueError:
                pass
        return True


def _float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
