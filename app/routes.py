"""Flask-Routen: Dashboard, Einstellungen, REST-API."""

import logging

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session

from . import database as db

logger = logging.getLogger(__name__)
from .crawler import run_crawl_async, is_running
from .scheduler import (
    get_next_run, get_next_runs, PLATFORMS,
    update_platform_schedules, update_digest_schedule, update_availability_schedule,
)

bp = Blueprint("main", __name__)

_PLATFORM_DISPLAY = {
    "kleinanzeigen": "Kleinanzeigen",
    "shpock": "Shpock",
    "vinted": "Vinted",
    "ebay": "eBay",
    "facebook": "Facebook",
}


def _build_platform_stats(settings: dict, next_runs: dict) -> list:
    """Baut die per-Plattform-Statusliste für Dashboard und API."""
    result = []
    for p in PLATFORMS:
        result.append({
            "id": p,
            "display": _PLATFORM_DISPLAY.get(p, p.capitalize()),
            "enabled": settings.get(f"{p}_enabled") == "1",
            "is_running": is_running(p),
            "last_crawl_end": settings.get(f"{p}_last_crawl_end", ""),
            "last_crawl_found": int(settings.get(f"{p}_last_crawl_found", 0) or 0),
            "next_run": next_runs.get(p, ""),
        })
    return result


# ── Dashboard ────────────────────────────────────────────────

@bp.route("/")
def index():
    # Wenn Profile existieren und kein Profil in Session → Auswahl
    if db.get_profiles() and "profile_id" not in session:
        return redirect(url_for("main.profiles_select"))

    search_terms = db.get_search_terms()
    settings = db.get_settings()

    max_age = int(settings.get("display_max_age_hours", 0) or 0)
    only_fav = request.args.get("favorites") == "1"
    only_free = request.args.get("free") == "1"

    listings = db.get_listings(
        limit=30,
        only_favorites=only_fav,
        only_free=only_free,
        max_age_hours=max_age,
    )

    # is_new: Anzeigen seit letztem Besuch des aktiven Profils markieren
    last_seen_at = session.get("profile_last_seen")
    for l in listings:
        l["is_new"] = bool(last_seen_at and l.get("found_at", "") > last_seen_at)

    last_found = sum(int(settings.get(f"{p}_last_crawl_found", 0) or 0) for p in PLATFORMS)
    next_runs = get_next_runs()
    platform_stats = _build_platform_stats(settings, next_runs)
    stats = {
        "total_listings": db.get_listing_count(),
        "last_crawl": settings.get("last_crawl_end", "") or "Noch kein Lauf",
        "next_crawl": get_next_run(),
        "crawl_status": settings.get("crawl_status", "idle"),
        "last_found": str(last_found),
    }
    price_stats = db.get_price_stats()
    return render_template(
        "index.html",
        search_terms=search_terms,
        listings=listings,
        stats=stats,
        platform_stats=platform_stats,
        price_stats=price_stats,
        only_fav=only_fav,
        only_free=only_free,
        active_profile=session.get("profile_name"),
        active_profile_emoji=session.get("profile_emoji"),
    )


# ── Suchbegriffe ─────────────────────────────────────────────

@bp.route("/terms", methods=["POST"])
def add_term():
    term = request.form.get("term", "").strip()
    if not term:
        return redirect(url_for("main.index"))
    if len(term) > 200:
        flash("Suchbegriff zu lang (max. 200 Zeichen).", "error")
        return redirect(url_for("main.index"))
    ok = db.add_search_term(term)
    if not ok:
        flash(f'"{term}" ist bereits vorhanden.', "warning")
    return redirect(url_for("main.index"))


@bp.route("/terms/<int:term_id>/delete", methods=["POST"])
def delete_term(term_id):
    db.delete_search_term(term_id)
    return redirect(url_for("main.index"))


@bp.route("/terms/<int:term_id>/toggle", methods=["POST"])
def toggle_term(term_id):
    db.toggle_search_term(term_id)
    return redirect(url_for("main.index"))


@bp.route("/terms/<int:term_id>/max-price", methods=["POST"])
def update_term_price(term_id):
    val = (request.json or {}).get("max_price")
    price = int(val) if val is not None and val != "" else None
    db.update_term_max_price(term_id, price)
    return jsonify({"status": "ok"})


# ── Favoriten ────────────────────────────────────────────────

@bp.route("/listings/<int:listing_id>/favorite", methods=["POST"])
def toggle_favorite(listing_id):
    db.toggle_favorite(listing_id)
    return jsonify({"status": "ok"})


@bp.route("/listings/<int:listing_id>/dismiss", methods=["POST"])
def dismiss_listing(listing_id):
    db.dismiss_listing(listing_id)
    return jsonify({"status": "ok"})


@bp.route("/listings/<int:listing_id>/note", methods=["POST"])
def update_note(listing_id):
    note = (request.json or {}).get("note", "")
    db.update_listing_note(listing_id, note)
    return jsonify({"status": "ok"})


# ── Einstellungen ────────────────────────────────────────────

@bp.route("/settings")
def settings_page():
    settings = db.get_settings()
    return render_template("settings.html", s=settings, profiles=db.get_profiles())


@bp.route("/settings", methods=["POST"])
def save_settings():
    allowed_keys = {
        "kleinanzeigen_enabled", "kleinanzeigen_max_price",
        "kleinanzeigen_location", "kleinanzeigen_radius", "kleinanzeigen_interval",
        "shpock_enabled", "shpock_max_price",
        "shpock_location", "shpock_radius", "shpock_interval",
        "facebook_enabled", "facebook_max_price", "facebook_location", "facebook_interval",
        "vinted_enabled", "vinted_max_price", "vinted_location", "vinted_radius", "vinted_interval",
        "ebay_enabled", "ebay_max_price", "ebay_location", "ebay_radius", "ebay_interval",
        "email_enabled", "email_subject_alert", "email_subject_digest",
        "email_smtp_server", "email_smtp_port",
        "email_sender", "email_password", "email_recipient",
        "crawler_interval", "crawler_max_results", "crawler_delay",
        "crawler_blacklist", "display_max_age_hours",
        "digest_enabled", "digest_time",
        "home_location",
        "availability_check_enabled", "availability_check_interval_hours",
        "ai_enabled", "ai_api_key", "ai_model", "ai_base_url",
    }
    data = {}
    for key in allowed_keys:
        if key.endswith("_enabled"):
            data[key] = "1" if request.form.get(key) else "0"
        else:
            val = request.form.get(key, "")
            if val is not None:
                data[key] = val

    db.save_settings(data)

    update_platform_schedules()
    update_digest_schedule()
    update_availability_schedule()

    flash("Einstellungen gespeichert.", "success")
    return redirect(url_for("main.settings_page"))


# ── Crawler-API ──────────────────────────────────────────────

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
        "platforms": _build_platform_stats(settings, next_runs),
    })


@bp.route("/api/platforms")
def api_platforms():
    return jsonify(db.get_distinct_platforms())


_VALID_SORTS = {"date_desc", "date_asc", "price_asc", "price_desc", "distance_asc"}


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

    listings = db.get_listings(
        limit=limit, offset=offset, search_terms=terms, platform=platform,
        only_favorites=only_fav, only_free=only_free, max_age_hours=max_age,
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
    from .logbuffer import get_lines
    return jsonify(get_lines())


@bp.route("/api/clear-listings", methods=["POST"])
def api_clear_listings():
    db.clear_all_listings()
    return jsonify({"status": "ok", "message": "Alle Anzeigen gelöscht (Favoriten behalten)."})


@bp.route("/api/listings/<int:listing_id>/contact-text", methods=["POST"])
def api_contact_text(listing_id):
    from .ai import generate_contact_text
    settings = db.get_settings()
    if not int(settings.get("ai_enabled", 0)):
        return jsonify({"error": "KI-Assistent ist nicht aktiviert."}), 403
    listing = db.get_listing_by_id(listing_id)
    if not listing:
        return jsonify({"error": "Anzeige nicht gefunden."}), 404
    price_stats = db.get_price_stats()
    text = generate_contact_text(listing, price_stats, settings)
    return jsonify({"text": text})


@bp.route("/api/ai-models")
def api_ai_models():
    """Holt verfügbare Modelle vom konfigurierten KI-Anbieter."""
    import requests as _req
    from .ai import _detect_provider

    settings = db.get_settings()
    api_key  = settings.get("ai_api_key",  "").strip()
    base_url = settings.get("ai_base_url", "").strip()
    model    = settings.get("ai_model",    "").strip()

    # API-Key-Prefix hat Vorrang vor Modellname
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
            resp = _req.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                timeout=6,
            )
            resp.raise_for_status()
            models = [m["id"] for m in resp.json().get("data", [])]

        elif provider == "openai":
            resp = _req.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=6,
            )
            resp.raise_for_status()
            all_ids = [m["id"] for m in resp.json().get("data", [])]
            models = sorted(m for m in all_ids if any(m.startswith(p) for p in ("gpt-", "o1", "o3", "o4")))

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
    from .checker import run_availability_check
    import threading
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
        from . import scrapers as _scrapers
        scraper_cls = getattr(_scrapers, cls_name)
        scraper = scraper_cls(settings)
        results = scraper.search(test_term, max_results=3)
        return jsonify({"status": "ok", "count": len(results),
                        "message": f"✓ {len(results)} Ergebnis(se) für \"{test_term}\""})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)[:300]}), 500


# ── Profile ──────────────────────────────────────────────────

@bp.route("/profiles/select")
def profiles_select():
    profiles = db.get_profiles()
    if not profiles:
        return redirect(url_for("main.index"))
    return render_template("profiles_select.html", profiles=profiles)


@bp.route("/profiles/select/<int:profile_id>", methods=["POST"])
def select_profile(profile_id):
    profile = db.get_profile(profile_id)
    if not profile:
        return redirect(url_for("main.profiles_select"))
    session["profile_id"] = profile_id
    session["profile_name"] = profile["name"]
    session["profile_emoji"] = profile["emoji"]
    session["profile_last_seen"] = profile["last_seen_at"]
    db.update_profile_last_seen(profile_id)
    return redirect(url_for("main.index"))


@bp.route("/profiles/logout", methods=["POST"])
def profile_logout():
    for key in ("profile_id", "profile_name", "profile_emoji", "profile_last_seen"):
        session.pop(key, None)
    profiles = db.get_profiles()
    if profiles:
        return redirect(url_for("main.profiles_select"))
    return redirect(url_for("main.index"))


@bp.route("/profiles", methods=["POST"])
def create_profile_route():
    name = request.form.get("name", "").strip()
    emoji = request.form.get("emoji", "👤").strip() or "👤"
    if not name:
        flash("Name darf nicht leer sein.", "error")
    elif len(name) > 50:
        flash("Name zu lang (max. 50 Zeichen).", "error")
    else:
        db.create_profile(name, emoji)
    return redirect(url_for("main.settings_page") + "#profiles")


@bp.route("/profiles/<int:profile_id>/update", methods=["POST"])
def update_profile_route(profile_id):
    data = request.json or {}
    name = data.get("name", "").strip()
    emoji = data.get("emoji", "👤").strip() or "👤"
    if not name or len(name) > 50:
        return jsonify({"error": "Ungültiger Name."}), 400
    db.update_profile(profile_id, name, emoji)
    if session.get("profile_id") == profile_id:
        session["profile_name"] = name
        session["profile_emoji"] = emoji
    return jsonify({"status": "ok"})


@bp.route("/profiles/<int:profile_id>/delete", methods=["POST"])
def delete_profile_route(profile_id):
    if session.get("profile_id") == profile_id:
        for key in ("profile_id", "profile_name", "profile_emoji", "profile_last_seen"):
            session.pop(key, None)
    db.delete_profile(profile_id)
    return jsonify({"status": "ok"})
