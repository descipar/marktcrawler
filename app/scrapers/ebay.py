"""Scraper für eBay.de (requests + BeautifulSoup)."""

import logging
import re
import time
from typing import List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing, _float, _int, price_within_limit, _large_image_url

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ebay.de"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


class EbayScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[float] = _float(settings.get("ebay_max_price"))
        self.location: str = settings.get("ebay_location", "").strip()
        self.radius_km: int = _int(settings.get("ebay_radius", 30)) or 30
        # Mindestabstand zwischen Suchanfragen (eBay sperrt bei zu schnellen Folge-Requests)
        self.request_delay: float = float(settings.get("ebay_request_delay", 10))
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._warmed_up = False
        self._last_request: float = 0.0

    def _warmup(self):
        """Homepage-Request zum Initialisieren der Session-Cookies (verhindert 403)."""
        if not self._warmed_up:
            try:
                self.session.get(f"{BASE_URL}/", timeout=10)
                # Referer setzen: Suchanfragen sehen aus wie Navigation von der Startseite
                self.session.headers["Referer"] = f"{BASE_URL}/"
                self.session.headers["Sec-Fetch-Site"] = "same-origin"
            except Exception:
                pass
            self._warmed_up = True

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        self._warmup()
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        url = self._build_url(term, max_results)
        logger.info(f"[eBay] '{term}' → {url}")
        try:
            r = self.session.get(url, timeout=15)
            self._last_request = time.monotonic()
            r.raise_for_status()
        except Exception as e:
            self._last_request = time.monotonic()
            logger.error(f"[eBay] Fehler bei '{term}': {e}")
            return []

        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select(".srp-river-results li.s-card")
        results = []
        for item in items[:max_results]:
            listing = self._parse(item, term)
            if listing and self._price_ok(listing):
                results.append(listing)
        logger.info(f"[eBay] {len(results)} Treffer für '{term}'.")
        return results

    def _build_url(self, term: str, max_results: int) -> str:
        keyword = quote_plus(term.strip())
        url = f"{BASE_URL}/sch/i.html?_nkw={keyword}&_sop=10&_ipg={min(max_results, 50)}"
        if self.location:
            url += f"&_stpos={quote_plus(self.location)}&_sadis={self.radius_km}"
        return url

    def _parse(self, item, term: str) -> Optional[Listing]:
        try:
            # img alt ist sauber (ohne "Neues Angebot"-Prefix)
            img_el = item.select_one("img.s-card__image")
            title = img_el.get("alt", "").strip() if img_el else ""
            if not title:
                title_el = item.select_one(".s-card__title .su-styled-text.primary")
                title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                return None

            link_el = item.select_one("a.s-card__link")
            url = link_el.get("href", "") if link_el else ""
            lid = item.get("data-listingid", "") or url[-20:]

            price_el = item.select_one(".s-card__price")
            price = price_el.get_text(strip=True) if price_el else "k.A."

            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-defer-load") or ""

            return Listing(
                platform="eBay",
                title=title,
                price=price,
                location="",
                url=url,
                listing_id=f"eb_{lid}",
                search_term=term,
                image_url=image_url,
                image_url_large=_large_image_url(image_url),
            )
        except Exception as e:
            logger.debug(f"[eBay] Parse-Fehler: {e}")
            return None

    def _price_ok(self, listing: Listing) -> bool:
        return price_within_limit(listing.price, self.max_price)
