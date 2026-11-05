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

# Alle Settings-Keys, die über das Einstellungsformular gesetzt werden können.
# Wird auch für Settings-Backup (Export/Import) als Whitelist verwendet.
SETTINGS_FORM_KEYS = frozenset({
    "kleinanzeigen_enabled", "kleinanzeigen_max_price",
    "kleinanzeigen_location", "kleinanzeigen_radius", "kleinanzeigen_interval", "kleinanzeigen_max_age_hours",
    "shpock_enabled", "shpock_max_price",
    "shpock_location", "shpock_radius", "shpock_interval", "shpock_max_age_hours",
    "facebook_enabled", "facebook_max_price", "facebook_location", "facebook_interval", "facebook_max_age_hours",
    "vinted_enabled", "vinted_max_price", "vinted_location", "vinted_radius", "vinted_interval", "vinted_max_age_hours",
    "ebay_enabled", "ebay_max_price", "ebay_location", "ebay_radius", "ebay_interval", "ebay_max_age_hours",
    "willhaben_enabled", "willhaben_max_price", "willhaben_location", "willhaben_radius",
    "willhaben_paylivery_only", "willhaben_interval", "willhaben_max_age_hours",
    "marktde_enabled", "marktde_max_price", "marktde_location", "marktde_radius",
    "marktde_interval", "marktde_max_age_hours",
    "email_enabled", "email_subject_alert", "email_subject_digest",
    "email_smtp_server", "email_smtp_port",
    "email_sender", "email_password",
    "crawler_interval", "crawler_max_results", "crawler_delay",
    "crawler_blacklist", "crawler_lang_filter_enabled", "crawler_lang_filter_langs",
    "display_max_age_hours",
    "digest_enabled", "digest_time",
    "home_location",
    "availability_check_enabled", "availability_check_interval_hours",
    "availability_check_workers", "availability_recheck_hours",
    "ai_enabled", "ai_api_key", "ai_model", "ai_base_url", "ai_prompt_hints",
    "server_url",
})

# Checkbox-Keys (HTML sendet keinen Wert, wenn nicht angehakt)
SETTINGS_BOOL_KEYS = frozenset(
    {k for k in SETTINGS_FORM_KEYS if k.endswith("_enabled")}
    | {"willhaben_paylivery_only", "crawler_lang_filter_enabled"}
)

# Zugangsdaten – werden beim Export nur auf ausdrücklichen Wunsch mitgenommen
SETTINGS_SECRET_KEYS = frozenset({"email_password", "ai_api_key"})


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
