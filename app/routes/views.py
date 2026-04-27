"""HTML-Routen: Dashboard, Einstellungen, Info-Seite, Suchbegriffe, Listing-Aktionen."""

import logging

from flask import render_template, request, jsonify, redirect, url_for, flash, session

from . import bp
from ._helpers import PLATFORMS, build_platform_max_ages, build_platform_stats, is_running
from .. import database as db
from ..scheduler import get_next_run, get_next_runs, update_platform_schedules, update_digest_schedule, update_availability_schedule

logger = logging.getLogger(__name__)


# ── Dashboard ────────────────────────────────────────────────

@bp.route("/")
def index():
    if db.get_profiles() and "profile_id" not in session:
        return redirect(url_for("main.profiles_select"))

    search_terms = db.get_search_terms()
    settings = db.get_settings()

    global_max_age = int(settings.get("display_max_age_hours", 0) or 0)
    only_fav = request.args.get("favorites") == "1"
    only_free = request.args.get("free") == "1"

    listings = db.get_listings(
        limit=30,
        only_favorites=only_fav,
        only_free=only_free,
        max_age_hours=global_max_age,
        platform_max_ages=None if global_max_age else build_platform_max_ages(settings),
    )

    last_seen_at = session.get("profile_last_seen")
    for l in listings:
        l["is_new"] = bool(last_seen_at and l.get("found_at", "") > last_seen_at)

    last_found = sum(int(settings.get(f"{p}_last_crawl_found", 0) or 0) for p in PLATFORMS)
    next_runs = get_next_runs()
    platform_stats = build_platform_stats(settings, next_runs)
    stats = {
        "total_listings": db.get_listing_count(),
        "last_crawl": settings.get("last_crawl_end", "") or "Noch kein Lauf",
        "next_crawl": get_next_run(),
        "crawl_status": settings.get("crawl_status", "idle"),
        "last_found": str(last_found),
    }
    return render_template(
        "index.html",
        search_terms=search_terms,
        listings=listings,
        stats=stats,
        platform_stats=platform_stats,
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
    price = None
    if val is not None and val != "":
        try:
            price = int(val)
            if not 0 <= price <= 100_000:
                return jsonify({"error": "Preis muss zwischen 0 und 100.000 liegen."}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Ungültiger Preiswert."}), 400
    db.update_term_max_price(term_id, price)
    return jsonify({"status": "ok"})


# ── Listing-Aktionen ─────────────────────────────────────────

@bp.route("/listings/<int:db_id>/favorite", methods=["POST"])
def toggle_favorite(db_id):
    db.toggle_favorite(db_id)
    return jsonify({"status": "ok"})


@bp.route("/listings/<int:db_id>/dismiss", methods=["POST"])
def dismiss_listing(db_id):
    db.dismiss_listing(db_id)
    return jsonify({"status": "ok"})


@bp.route("/listings/<int:db_id>/note", methods=["POST"])
def update_note(db_id):
    note = (request.json or {}).get("note", "")
    db.update_listing_note(db_id, note)
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
        "kleinanzeigen_location", "kleinanzeigen_radius", "kleinanzeigen_interval", "kleinanzeigen_max_age_hours",
        "shpock_enabled", "shpock_max_price",
        "shpock_location", "shpock_radius", "shpock_interval", "shpock_max_age_hours",
        "facebook_enabled", "facebook_max_price", "facebook_location", "facebook_interval", "facebook_max_age_hours",
        "vinted_enabled", "vinted_max_price", "vinted_location", "vinted_radius", "vinted_interval", "vinted_max_age_hours",
        "ebay_enabled", "ebay_max_price", "ebay_location", "ebay_radius", "ebay_interval", "ebay_max_age_hours",
        "email_enabled", "email_subject_alert", "email_subject_digest",
        "email_smtp_server", "email_smtp_port",
        "email_sender", "email_password", "email_recipient",
        "crawler_interval", "crawler_max_results", "crawler_delay",
        "crawler_blacklist", "display_max_age_hours",
        "digest_enabled", "digest_time",
        "home_location",
        "availability_check_enabled", "availability_check_interval_hours",
        "availability_check_workers", "availability_recheck_hours",
        "ai_enabled", "ai_api_key", "ai_model", "ai_base_url", "ai_prompt_hints",
        "server_url",
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


# ── Info & Statistik ─────────────────────────────────────────

@bp.route("/info")
def info():
    from app.version import get_current_version, _github_repo
    stats = db.get_system_stats()
    price_stats = db.get_price_stats()
    version = get_current_version()
    repo = _github_repo()
    repo_url = f"https://github.com/{repo}" if repo else ""
    return render_template("info.html", stats=stats, price_stats=price_stats,
                           version=version, repo_url=repo_url)
