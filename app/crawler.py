"""Orchestriert einen Crawl-Durchlauf über alle aktivierten Plattformen."""

import logging
import threading
import time
from datetime import datetime
from typing import List

from . import database as db
from .notifier import notify
from .scrapers import KleinanzeigenScraper, ShpockScraper, FacebookScraper
from .scrapers.base import Listing

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_running = False


def is_running() -> bool:
    return _running


def run_crawl() -> dict:
    """
    Führt einen vollständigen Crawl-Durchlauf durch.
    Thread-sicher via Lock. Gibt Statistiken zurück.
    """
    global _running

    with _lock:
        if _running:
            logger.warning("Crawl läuft bereits – übersprungen.")
            return {"status": "already_running", "new": 0}
        _running = True

    stats = {"new": 0, "total": 0, "errors": 0}
    db.set_setting("crawl_status", "running")
    db.set_setting("last_crawl_start", datetime.now().isoformat(timespec="seconds"))

    try:
        settings = db.get_settings()
        search_terms = db.get_search_terms(enabled_only=True)
        delay = float(settings.get("crawler_delay", 2))
        max_results = int(settings.get("crawler_max_results", 20))

        if not search_terms:
            logger.warning("Keine aktiven Suchbegriffe vorhanden.")
            return {"status": "no_terms", "new": 0}

        # Scraper nach aktivierten Plattformen aufbauen
        scrapers = []
        if settings.get("kleinanzeigen_enabled") == "1":
            scrapers.append(KleinanzeigenScraper(settings))
        if settings.get("shpock_enabled") == "1":
            scrapers.append(ShpockScraper(settings))
        if settings.get("facebook_enabled") == "1":
            scrapers.append(FacebookScraper(settings))

        if not scrapers:
            logger.warning("Keine Plattform aktiviert.")
            return {"status": "no_platforms", "new": 0}

        logger.info(
            f"Crawl startet: {len(search_terms)} Begriffe × {len(scrapers)} Plattformen"
        )

        new_listings: List[Listing] = []

        for scraper in scrapers:
            for term_row in search_terms:
                term = term_row["term"]
                try:
                    listings = scraper.search(term, max_results=max_results)
                    stats["total"] += len(listings)
                    for listing in listings:
                        if db.save_listing(listing):
                            stats["new"] += 1
                            new_listings.append(listing)
                except Exception as e:
                    logger.error(f"Fehler bei {scraper.__class__.__name__} / '{term}': {e}")
                    stats["errors"] += 1
                time.sleep(delay)

        # Alte Einträge aufräumen (älter als 30 Tage)
        db.clear_old_listings(days=30)

        # E-Mail falls neue Treffer
        if new_listings:
            notify(new_listings, settings)

        logger.info(
            f"Crawl beendet: {stats['new']} neue / {stats['total']} gesamt "
            f"/ {stats['errors']} Fehler"
        )

    except Exception as e:
        logger.error(f"Unerwarteter Crawl-Fehler: {e}", exc_info=True)
        stats["errors"] += 1
    finally:
        _running = False
        db.set_setting("crawl_status", "idle")
        db.set_setting("last_crawl_end", datetime.now().isoformat(timespec="seconds"))
        db.set_setting("last_crawl_found", str(stats["new"]))

    return {"status": "ok", **stats}


def run_crawl_async() -> threading.Thread:
    """Startet den Crawl in einem Background-Thread."""
    t = threading.Thread(target=run_crawl, daemon=True, name="crawler")
    t.start()
    return t
