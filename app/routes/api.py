"""REST-API-Routen (/api/*)."""

import logging
import threading

from flask import request, jsonify, session

from . import bp
from ._helpers import PLATFORMS, build_platform_max_ages, build_platform_stats, is_running
from .. import database as db
from ..crawler import run_crawl_async
from ..scheduler import get_next_run, get_next_runs

logger = logging.getLogger(__name__)

_VALID_SORTS = {"date_desc", "date_asc", "price_asc", "price_desc", "distance_asc"}


@bp.route("/api/crawl", methods=["POST"])
def api_crawl():
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "all")

    if platform == "all":
        settings = db.get_settings()
        started = [p for p in PLATFORMS if settings.get(f"{p}_enabled") == "1" and not is_running(p)]
        if not started:
            return jsonify({"status": "already_running", "message": "Alle aktiven Crawls laufen bereits."}), 409
        for p in started:
            run_crawl_async(p, manual=True)
        return jsonify({"status": "started", "message": f"Gestartet: {', '.join(started)}"})

    if platform not in PLATFORMS:
        return jsonify({"status": "error", "message": "Unbekannte Plattform."}), 400
    if is_running(platform):
        return jsonify({"status": "already_running", "message": f"{platform} läuft bereits."}), 409
    run_crawl_async(platform, manual=True)
    return jsonify({"status": "started", "message": f"{platform} gestartet."})


@bp.route("/api/status")
def api_status():
    settings = db.get_settings()
    next_runs = get_next_runs()
    return jsonify({
        "crawl_status": settings.get("crawl_status", "idle"),
        "last_crawl": settings.get("last_crawl_end", ""),
        "next_crawl": get_next_run(),
        "next_runs": next_runs,
        "last_found": str(sum(int(settings.get(f"{p}_last_crawl_found", 0) or 0) for p in PLATFORMS)),
        "total_listings": db.get_listing_count(),
        "is_running": is_running(),
        "platform_counts": db.get_platform_counts(),
        "platforms": build_platform_stats(settings, next_runs),
    })


@bp.route("/api/platforms")
def api_platforms():
    return jsonify(db.get_distinct_platforms())


@bp.route("/api/listings")
def api_listings():
    terms = request.args.getlist("term") or None
    platform = request.args.get("platform")
    sort_by = request.args.get("sort", "date_desc")
    if sort_by not in _VALID_SORTS:
        sort_by = "date_desc"
    exclude_text = request.args.get("exclude", "").strip() or None
    try:
        limit = int(request.args.get("limit", 30))
        offset = int(request.args.get("offset", 0))
        max_age = int(request.args.get("max_age", 0) or 0)
        max_dist_raw = request.args.get("max_distance", "")
        max_distance = float(max_dist_raw) if max_dist_raw else None
    except ValueError:
        return jsonify({"error": "Ungültiger Parameter."}), 400
    only_fav = request.args.get("favorites") == "1"
    only_free = request.args.get("free") == "1"
    only_new = request.args.get("new") == "1"
    last_seen_at = session.get("profile_last_seen") if only_new else None

    platform_max_ages = None
    if not max_age:
        settings = db.get_settings()
        platform_max_ages = build_platform_max_ages(settings)

    listings = db.get_listings(
        limit=limit, offset=offset, search_terms=terms, platform=platform,
        only_favorites=only_fav, only_free=only_free, max_age_hours=max_age,
        platform_max_ages=platform_max_ages,
        max_distance_km=max_distance, sort_by=sort_by, exclude_text=exclude_text,
        since_datetime=last_seen_at,
    )
    last_seen_at = session.get("profile_last_seen")
    for l in listings:
        l["is_new"] = bool(last_seen_at and l.get("found_at", "") > last_seen_at)
    return jsonify(listings)


@bp.route("/api/stats")
def api_stats():
    return jsonify(db.get_price_stats())


@bp.route("/api/log")
def api_log():
    from ..logbuffer import get_lines
    return jsonify(get_lines())


@bp.route("/api/clear-listings", methods=["POST"])
def api_clear_listings():
    db.clear_all_listings()
    return jsonify({"status": "ok", "message": "Alle Anzeigen gelöscht (Favoriten behalten)."})


@bp.route("/api/listings/<int:db_id>/contact-text", methods=["POST"])
def api_contact_text(db_id):
    from ..ai import generate_contact_text
    settings = db.get_settings()
    if not int(settings.get("ai_enabled", 0)):
        return jsonify({"error": "KI-Assistent ist nicht aktiviert."}), 403
    listing = db.get_listing_by_id(db_id)
    if not listing:
        return jsonify({"error": "Anzeige nicht gefunden."}), 404
    price_stats = db.get_price_stats()
    text = generate_contact_text(listing, price_stats, settings)
    return jsonify({"text": text})


@bp.route("/api/ai-models")
def api_ai_models():
    """Holt verfügbare Modelle vom konfigurierten KI-Anbieter."""
    import requests as _req
    from ..ai import _detect_provider

    settings = db.get_settings()
    api_key  = settings.get("ai_api_key",  "").strip()
    base_url = settings.get("ai_base_url", "").strip()
    model    = settings.get("ai_model",    "").strip()

    if base_url:
        provider = "ollama"
    elif api_key.startswith("sk-ant-"):
        provider = "anthropic"
    elif api_key.startswith("sk-"):
        provider = "openai"
    else:
        provider = _detect_provider(model, base_url)

    try:
        if provider == "anthropic":
            import re as _re
            resp = _req.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                timeout=6,
            )
            resp.raise_for_status()
            _ant_exclude = _re.compile(r"claude-[012][^-]|instant|legacy", _re.I)
            models = [
                m["id"] for m in resp.json().get("data", [])
                if not _ant_exclude.search(m["id"])
            ]

        elif provider == "openai":
            import re as _re
            resp = _req.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=6,
            )
            resp.raise_for_status()
            _oai_keep = _re.compile(r"^(gpt-4o|gpt-4-turbo|o[1-9]|o[1-9]-mini|o[1-9]-pro)", _re.I)
            _oai_skip = _re.compile(r"audio|realtime|tts|whisper|dall|embed|instruct|search|\d{4}-\d{2}-\d{2}", _re.I)
            all_ids = [m["id"] for m in resp.json().get("data", [])]
            models = sorted(m for m in all_ids if _oai_keep.match(m) and not _oai_skip.search(m))

        elif provider == "ollama":
            ollama_root = base_url.rstrip("/").removesuffix("/v1")
            resp = _req.get(f"{ollama_root}/api/tags", timeout=6)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]

        else:
            models = []

        return jsonify({"provider": provider, "models": models})

    except Exception as exc:
        return jsonify({"provider": provider, "models": [], "error": str(exc)}), 200


@bp.route("/api/availability-check", methods=["POST"])
def api_availability_check():
    from ..checker import run_availability_check
    t = threading.Thread(target=run_availability_check, daemon=True, name="availability-check")
    t.start()
    return jsonify({"status": "started", "message": "Verfügbarkeits-Check gestartet."})


@bp.route("/api/clear-listings-by-age", methods=["POST"])
def api_clear_listings_by_age():
    try:
        hours = int((request.get_json(silent=True) or {}).get("hours", 0))
        if hours <= 0:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        return jsonify({"error": "Ungültiger Wert für hours."}), 400
    logger.info(f"🗑️ Löschung gestartet: Anzeigen älter als {hours}h …")
    deleted = db.clear_listings_older_than(hours)
    logger.info(f"🗑️ Fertig: {deleted} Anzeige(n) gelöscht und als gesehen markiert.")
    return jsonify({"status": "ok", "deleted": deleted,
                    "message": f"{deleted} Anzeigen gelöscht (älter als {hours}h)."})


@bp.route("/api/test-scraper", methods=["POST"])
def api_test_scraper():
    platform = (request.json or {}).get("platform", "")
    settings = db.get_settings()
    terms = db.get_search_terms(enabled_only=True)
    test_term = terms[0]["term"] if terms else "baby"
    scraper_map = {
        "kleinanzeigen": "KleinanzeigenScraper",
        "shpock": "ShpockScraper",
        "vinted": "VintedScraper",
        "ebay": "EbayScraper",
        "facebook": "FacebookScraper",
    }
    cls_name = scraper_map.get(platform)
    if not cls_name:
        return jsonify({"status": "error", "message": "Unbekannte Plattform."}), 400
    try:
        from .. import scrapers as _scrapers
        scraper_cls = getattr(_scrapers, cls_name)
        scraper = scraper_cls(settings)
        results = scraper.search(test_term, max_results=3)
        return jsonify({"status": "ok", "count": len(results),
                        "message": f"✓ {len(results)} Ergebnis(se) für \"{test_term}\""})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)[:300]}), 500


@bp.route("/api/check-updates")
def check_updates():
    from ..version import get_current_version, get_available_updates
    version = get_current_version()
    updates = get_available_updates(version["hash"])
    if updates is None:
        return jsonify({"status": "error", "message": "GitHub nicht erreichbar oder Repo unbekannt."})
    return jsonify({"status": "ok", "updates": updates, "count": len(updates)})
