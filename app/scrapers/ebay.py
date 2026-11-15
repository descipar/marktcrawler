"""Scraper für eBay.de (curl_cffi + BeautifulSoup).

eBay schützt die Suche mit Akamai Bot Manager, der Clients am TLS-/HTTP2-
Fingerprint erkennt. ``requests`` wird dort pauschal mit 403 abgewiesen –
unabhängig von Headern oder IP. ``curl_cffi`` imitiert den Fingerprint eines
echten Browsers. Firefox und Safari kommen durch, Chrome/Edge-Profile werden
(Stand 11/2026) ebenfalls geblockt – daher die Profil-Reihenfolge unten.
"""

import logging
import time
from typing import List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from .base import BaseScraper, Listing, _float, _int, price_within_limit, _large_image_url

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ebay.de"
# Browser-Profile für curl_cffi, in Reihenfolge der Präferenz. Bei 403 wird
# auf das nächste Profil gewechselt.
IMPERSONATE_PROFILES = ("firefox", "safari")
# Nur Sprache setzen – User-Agent & Co. liefert das Impersonate-Profil passend
# zum Fingerprint. Ein abweichender User-Agent würde Akamai erst recht auffallen.
HEADERS = {"Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"}


class EbayScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[float] = _float(settings.get("ebay_max_price"))
        self.location: str = settings.get("ebay_location", "").strip()
        self.radius_km: int = _int(settings.get("ebay_radius", 30)) or 30
        # Mindestabstand zwischen Suchanfragen (eBay sperrt bei zu schnellen Folge-Requests)
        self.request_delay: float = float(settings.get("ebay_request_delay", 10))
        self._profile_idx = 0
        self.session = self._new_session()
        self._warmed_up = False
        self._last_request: float = 0.0

    def _new_session(self):
        session = cffi_requests.Session(impersonate=IMPERSONATE_PROFILES[self._profile_idx])
        session.headers.update(HEADERS)
        return session

    def _switch_profile(self) -> bool:
        """Wechselt auf das nächste Browser-Profil. False, wenn keins mehr übrig ist."""
        if self._profile_idx + 1 >= len(IMPERSONATE_PROFILES):
            return False
        self._profile_idx += 1
        logger.info(f"[eBay] 403 – wechsle auf Browser-Profil '{IMPERSONATE_PROFILES[self._profile_idx]}'.")
        self.session = self._new_session()
        self._warmed_up = False
        return True

    def _warmup(self):
        """Homepage-Request zum Initialisieren der Session-Cookies (Akamai bm_*)."""
        if not self._warmed_up:
            try:
                self.session.get(f"{BASE_URL}/", timeout=15)
                # Referer setzen: Suchanfragen sehen aus wie Navigation von der Startseite
                self.session.headers["Referer"] = f"{BASE_URL}/"
            except Exception:
                pass
            self._warmed_up = True

    def _fetch(self, url: str):
        """GET mit Warmup; bei 403 einmal pro verbleibendem Browser-Profil neu versuchen."""
        while True:
            self._warmup()
            r = self.session.get(url, timeout=20)
            if r.status_code == 403 and self._switch_profile():
                continue
            r.raise_for_status()
            return r

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        url = self._build_url(term, max_results)
        logger.info(f"[eBay] '{term}' → {url}")
        try:
            r = self._fetch(url)
            self._last_request = time.monotonic()
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
