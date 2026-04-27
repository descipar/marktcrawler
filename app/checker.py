"""Verfügbarkeits-Check: prüft ob gespeicherte Anzeigen noch online sind."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

from . import database as db

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_running = False

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; marktcrawler/1.0)"}
_GONE_CODES = {404, 410}
_TIMEOUT = 6
_MIN_AGE_MINUTES = 60  # frisch gecrawlte Anzeigen nicht sofort prüfen


def is_running() -> bool:
    with _lock:
        return _running


def _check_one(row: dict) -> tuple[str, str | None]:
    """Prüft eine URL. Gibt (listing_id, 'delete' | 'ok' | 'error') zurück."""
    url = row.get("url", "")
    if not url or not url.startswith("http"):
        return row["listing_id"], "skip"
    try:
        resp = requests.head(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        if resp.status_code in _GONE_CODES:
            return row["listing_id"], "delete"
        return row["listing_id"], "ok"
    except requests.exceptions.RequestException:
        return row["listing_id"], "error"


def run_availability_check() -> dict:
    """
    Prüft Anzeigen parallel via HEAD-Request.
    Löscht Einträge (inkl. Favoriten) bei HTTP 404/410.
    Überspringt Anzeigen jünger als _MIN_AGE_MINUTES oder bereits geprüft
    innerhalb von recheck_hours (Standard 48h = 2 Tage).
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

        workers = max(1, int(settings.get("availability_check_workers", 5) or 5))
        recheck_hours = max(0, int(settings.get("availability_recheck_hours", 48) or 48))

        listings = db.get_all_listing_urls(
            min_age_minutes=_MIN_AGE_MINUTES,
            recheck_hours=recheck_hours,
        )
        stats = {"checked": 0, "deleted": 0, "errors": 0}

        if not listings:
            logger.info("Verfügbarkeits-Check: keine fälligen Anzeigen.")
            db.set_setting("availability_last_run", datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"))
            db.set_setting("availability_last_checked", "0")
            db.set_setting("availability_last_deleted", "0")
            return {"status": "ok", **stats}

        est_min = len(listings) / workers * _TIMEOUT / 60
        logger.info(
            f"Verfügbarkeits-Check startet: {len(listings)} Anzeigen "
            f"({workers} parallel, ~{est_min:.0f} Min. max)"
        )

        checked_ids: list[str] = []

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_check_one, row): row for row in listings}
            for future in as_completed(futures):
                listing_id, result = future.result()
                if result == "delete":
                    db.delete_listing_by_listing_id(listing_id)
                    stats["deleted"] += 1
                    logger.debug(f"Anzeige entfernt (404/410): {futures[future].get('title', '')[:60]}")
                elif result == "ok":
                    stats["checked"] += 1
                    checked_ids.append(listing_id)
                elif result == "error":
                    stats["errors"] += 1
                    checked_ids.append(listing_id)  # auch bei Fehler als geprüft markieren

        db.mark_listings_availability_checked(checked_ids)

        logger.info(
            f"Verfügbarkeits-Check beendet: {stats['checked']} geprüft, "
            f"{stats['deleted']} gelöscht, {stats['errors']} Fehler"
        )
        db.set_setting("availability_last_run", datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"))
        db.set_setting("availability_last_checked", str(stats["checked"] + stats["deleted"]))
        db.set_setting("availability_last_deleted", str(stats["deleted"]))
        return {"status": "ok", **stats}

    finally:
        with _lock:
            _running = False
