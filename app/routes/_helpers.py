"""Gemeinsame Hilfsfunktionen und Konstanten für alle Route-Module."""

import logging
from typing import Dict

from ..crawler import is_running
from ..scheduler import PLATFORMS, get_next_run, get_next_runs

logger = logging.getLogger(__name__)

_PLATFORM_DISPLAY = {
    "kleinanzeigen": "Kleinanzeigen",
    "shpock": "Shpock",
    "vinted": "Vinted",
    "ebay": "eBay",
    "facebook": "Facebook",
    "willhaben": "Willhaben",
    "marktde": "markt.de",
}


def build_platform_max_ages(settings: dict) -> Dict[str, int]:
    return {
        p: int(settings.get(f"{p}_max_age_hours", 0) or 0)
        for p in PLATFORMS
    }


def build_platform_stats(settings: dict, next_runs: dict) -> list:
    result = []
    for p in PLATFORMS:
        result.append({
            "id": p,
            "display": _PLATFORM_DISPLAY.get(p, p.capitalize()),
            "enabled": settings.get(f"{p}_enabled") == "1",
            "is_running": is_running(p),
            "last_crawl_end": settings.get(f"{p}_last_crawl_end", ""),
            "last_crawl_found": int(settings.get(f"{p}_last_crawl_found", 0) or 0),
            "last_crawl_duration": int(settings.get(f"{p}_last_crawl_duration", 0) or 0),
            "next_run": next_runs.get(p, ""),
        })
    return result
