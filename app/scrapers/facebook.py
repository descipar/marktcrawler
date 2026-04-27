"""
Scraper für Facebook Marketplace (Playwright – headless).
Benötigt einmaligen Login: docker exec -it marktcrawler python -c
  "from app.scrapers.facebook import FacebookScraper; FacebookScraper({}).interactive_login()"
"""

import logging
import os
import re
import time
from pathlib import Path
from typing import List, Optional

from .base import BaseScraper, Listing, _int

logger = logging.getLogger(__name__)
SESSION_FILE = Path(os.environ.get("DATA_DIR", "/data")) / "facebook_session.json"


class FacebookScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[int] = _int(settings.get("facebook_max_price"))
        self.location: str = settings.get("facebook_location", "")

    def _playwright_ok(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def interactive_login(self):
        if not self._playwright_ok():
            print("Playwright fehlt. Installiere: pip install playwright && playwright install chromium")
            return
        from playwright.sync_api import sync_playwright
        print("\nBrowser öffnet sich – bitte einloggen, danach ENTER drücken.\n")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context()
            ctx.new_page().goto("https://www.facebook.com/login")
            input("ENTER drücken nach erfolgreichem Login: ")
            ctx.storage_state(path=str(SESSION_FILE))
            browser.close()
        print(f"Session gespeichert: {SESSION_FILE}")

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        if not self._playwright_ok():
            logger.warning("[Facebook] Playwright nicht installiert – übersprungen.")
            return []
        if not SESSION_FILE.exists():
            logger.warning("[Facebook] Keine Session – bitte erst --fb-login ausführen.")
            return []

        from playwright.sync_api import sync_playwright
        listings: List[Listing] = []
        logger.info(f"[Facebook] '{term}'")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(storage_state=str(SESSION_FILE))
                page = ctx.new_page()
                encoded = term.replace(" ", "%20")
                url = f"https://www.facebook.com/marketplace/search?query={encoded}&sortBy=creation_time_descend"
                if self.max_price:
                    url += f"&maxPrice={self.max_price}"
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(3)
                items = page.query_selector_all("div[data-testid='marketplace_feed_item']")
                if not items:
                    items = page.query_selector_all("div.x3ct3a4")
                logger.info(f"[Facebook] {len(items)} Treffer für '{term}'.")
                for item in items[:max_results]:
                    l = self._parse(item)
                    if l and self._price_ok(l):
                        l.search_term = term
                        listings.append(l)
                browser.close()
        except Exception as e:
            logger.error(f"[Facebook] Fehler: {e}")
        return listings

    def _parse(self, item) -> Optional[Listing]:
        try:
            title_el = item.query_selector("span.x1lliihq") or item.query_selector("span")
            title = title_el.inner_text() if title_el else "Unbekannt"
            spans = item.query_selector_all("span")
            price = "k.A."
            for s in spans:
                t = s.inner_text().strip()
                if "€" in t:
                    price = t
                    break
            link_el = item.query_selector("a")
            href = link_el.get_attribute("href") if link_el else ""
            if href and not href.startswith("http"):
                href = "https://www.facebook.com" + href
            m = re.search(r"/item/(\d+)", href or "")
            lid = m.group(1) if m else (href or "")[-20:]
            img_el = item.query_selector("img")
            return Listing(
                platform="Facebook", title=title, price=price,
                location=self.location, url=href or "",
                listing_id=f"fb_{lid}",
                image_url=img_el.get_attribute("src") if img_el else "",
            )
        except Exception as e:
            logger.debug(f"[Facebook] Parse-Fehler: {e}")
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


