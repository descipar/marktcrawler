"""Orchestriert einen Crawl-Durchlauf über alle aktivierten Plattformen."""

import logging
import re
import threading
import time
from datetime import datetime
from typing import List

from . import database as db
from .geo import distance_to_home
from .notifier import notify
from .scrapers import KleinanzeigenScraper, ShpockScraper, FacebookScraper, VintedScraper, EbayScraper
from .scrapers.base import Listing

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_running = False

_FREE_PRICE_RE = re.compile(
    r"^\s*(0\s*€?|0,00\s*€?|kostenlos|gratis|umsonst|zu\s+verschenken|verschenken|free)\s*$",
    re.IGNORECASE,
)
_FREE_TEXT_RE = re.compile(
    r"\b(zu\s+verschenken|verschenke|kostenlos|gratis|umsonst|zu\s+vergeben)\b",
    re.IGNORECASE,
)


def is_running() -> bool:
    with _lock:
        return _running


def _is_free(listing: Listing) -> bool:
    if _FREE_PRICE_RE.match(listing.price or ""):
        return True
    if _FREE_TEXT_RE.search(listing.title or ""):
        return True
    if _FREE_TEXT_RE.search(listing.description or ""):
        return True
    return False


def _is_blacklisted(listing: Listing, blacklist: List[str]) -> bool:
    if not blacklist:
        return False
    text = f"{listing.title} {listing.description}".lower()
    return any(term.lower() in text for term in blacklist)


def run_crawl() -> dict:
    global _running

    with _lock:
        if _running:
            logger.warning("Crawl läuft bereits – übersprungen.")
            return {"status": "already_running", "new": 0}
        _running = True

    stats = {"new": 0, "total": 0, "errors": 0, "skipped_blacklist": 0, "free": 0}
    db.set_setting("crawl_status", "running")
    db.set_setting("last_crawl_start", datetime.now().isoformat(timespec="seconds"))

    try:
        settings = db.get_settings()
        search_terms = db.get_search_terms(enabled_only=True)
        delay = float(settings.get("crawler_delay", 2))
        max_results = int(settings.get("crawler_max_results", 20))

        raw_blacklist = settings.get("crawler_blacklist", "")
        # Textarea sendet Zeilenumbrüche; Komma als Fallback für alte Daten
        blacklist = [w.strip() for w in re.split(r"[\n,]", raw_blacklist) if w.strip()]

        if not search_terms:
            logger.warning("Keine aktiven Suchbegriffe.")
            return {"status": "no_terms", "new": 0}

        scrapers = []
        if settings.get("kleinanzeigen_enabled") == "1":
            scrapers.append(KleinanzeigenScraper(settings))
        if settings.get("shpock_enabled") == "1":
            scrapers.append(ShpockScraper(settings))
        if settings.get("facebook_enabled") == "1":
            scrapers.append(FacebookScraper(settings))
        if settings.get("vinted_enabled") == "1":
            scrapers.append(VintedScraper(settings))
        if settings.get("ebay_enabled") == "1":
            scrapers.append(EbayScraper(settings))

        if not scrapers:
            logger.warning("Keine Plattform aktiviert.")
            return {"status": "no_platforms", "new": 0}

        logger.info(
            f"Crawl startet: {len(search_terms)} Begriffe × {len(scrapers)} Plattform(en)"
        )

        new_listings: List[Listing] = []

        for scraper in scrapers:
            for term_row in search_terms:
                term = term_row["term"]
                try:
                    listings = scraper.search(term, max_results=max_results)
                    stats["total"] += len(listings)

                    for listing in listings:
                        if _is_blacklisted(listing, blacklist):
                            stats["skipped_blacklist"] += 1
                            logger.debug(f"Blacklist: '{listing.title}'")
                            continue

                        listing.is_free = _is_free(listing)
                        if listing.is_free:
                            stats["free"] += 1

                        if db.save_listing(listing):
                            stats["new"] += 1
                            new_listings.append(listing)

                            # Entfernung berechnen und speichern
                            if listing.location:
                                try:
                                    dist = distance_to_home(listing.location, settings)
                                    if dist is not None:
                                        db.update_listing_distance(listing.listing_id, dist)
                                        listing.distance_km = round(dist, 1)
                                except Exception:
                                    pass

                except Exception as e:
                    logger.error(f"Fehler bei {scraper.__class__.__name__} / '{term}': {e}")
                    stats["errors"] += 1
                time.sleep(delay)

        db.clear_old_listings(days=30)

        if new_listings:
            notify(new_listings, settings)

        logger.info(
            f"Crawl beendet: {stats['new']} neu / {stats['total']} gesamt / "
            f"{stats['skipped_blacklist']} Blacklist / {stats['free']} gratis / "
            f"{stats['errors']} Fehler"
        )

    except Exception as e:
        logger.error(f"Unerwarteter Crawl-Fehler: {e}", exc_info=True)
        stats["errors"] += 1
    finally:
        with _lock:
            _running = False
        db.set_setting("crawl_status", "idle")
        db.set_setting("last_crawl_end", datetime.now().isoformat(timespec="seconds"))
        db.set_setting("last_crawl_found", str(stats["new"]))

    return {"status": "ok", **stats}


def run_crawl_async() -> threading.Thread:
    t = threading.Thread(target=run_crawl, daemon=True, name="crawler")
    t.start()
    return t
