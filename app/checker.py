"""Verfügbarkeits-Check: prüft ob gespeicherte Anzeigen noch online sind."""

import logging
import threading
import time

import requests

from . import database as db

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_running = False

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; baby-crawler/1.0)"}
_GONE_CODES = {404, 410}
_TIMEOUT = 8
_DELAY = 0.5
_MIN_AGE_MINUTES = 60  # frisch gecrawlte Anzeigen nicht sofort prüfen


def is_running() -> bool:
    with _lock:
        return _running


def run_availability_check() -> dict:
    """
    Prüft alle Anzeigen in der DB via HEAD-Request.
    Löscht Einträge (inkl. Favoriten) bei HTTP 404/410.
    Netzwerkfehler oder andere Status-Codes → Eintrag bleibt erhalten.
    Überspringt Anzeigen die jünger als _MIN_AGE_MINUTES sind.
    """
    global _running

    with _lock:
        if _running:
            logger.warning("Verfügbarkeits-Check läuft bereits – übersprungen.")
            return {"status": "already_running", "checked": 0, "deleted": 0, "errors": 0}
        _running = True

    try:
        settings = db.get_settings()
        if settings.get("availability_check_enabled", "1") != "1":
            logger.debug("Verfügbarkeits-Check deaktiviert.")
            return {"status": "disabled", "checked": 0, "deleted": 0, "errors": 0}

        listings = db.get_all_listing_urls(min_age_minutes=_MIN_AGE_MINUTES)
        stats = {"checked": 0, "deleted": 0, "errors": 0}

        est_min = len(listings) * _DELAY / 60
        logger.info(f"Verfügbarkeits-Check startet: {len(listings)} Anzeigen (~{est_min:.0f} Min.)")

        for row in listings:
            url = row.get("url", "")
            if not url or not url.startswith("http"):
                continue
            try:
                resp = requests.head(
                    url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True
                )
                stats["checked"] += 1
                if resp.status_code in _GONE_CODES:
                    db.delete_listing_by_listing_id(row["listing_id"])
                    stats["deleted"] += 1
                    logger.debug(
                        f"Anzeige entfernt (HTTP {resp.status_code}): "
                        f"{row.get('title', '')[:60]}"
                    )
            except requests.exceptions.RequestException as e:
                logger.debug(f"Check-Fehler für '{url[:60]}': {e}")
                stats["errors"] += 1

            time.sleep(_DELAY)

        logger.info(
            f"Verfügbarkeits-Check beendet: {stats['checked']} geprüft, "
            f"{stats['deleted']} gelöscht, {stats['errors']} Fehler"
        )
        return {"status": "ok", **stats}

    finally:
        with _lock:
            _running = False
