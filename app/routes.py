"""Flask-Routen: Dashboard, Einstellungen, REST-API."""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash

from . import database as db
from .crawler import run_crawl_async, is_running
from .scheduler import get_next_run, update_interval, update_digest_schedule

bp = Blueprint("main", __name__)


# ── Dashboard ────────────────────────────────────────────────

@bp.route("/")
def index():
    search_terms = db.get_search_terms()
    settings = db.get_settings()

    max_age = int(settings.get("crawler_max_age_hours", 0) or 0)
    only_fav = request.args.get("favorites") == "1"
    only_free = request.args.get("free") == "1"

    listings = db.get_listings(
        limit=60,
        only_favorites=only_fav,
        only_free=only_free,
        max_age_hours=max_age,
    )
    stats = {
        "total_listings": db.get_listing_count(),
        "last_crawl": settings.get("last_crawl_end", "") or "Noch kein Lauf",
        "next_crawl": get_next_run(),
        "crawl_status": settings.get("crawl_status", "idle"),
        "last_found": settings.get("last_crawl_found", "0"),
    }
    price_stats = db.get_price_stats()
    return render_template(
        "index.html",
        search_terms=search_terms,
        listings=listings,
        stats=stats,
        price_stats=price_stats,
        only_fav=only_fav,
        only_free=only_free,
    )


# ── Suchbegriffe ─────────────────────────────────────────────

@bp.route("/terms", methods=["POST"])
def add_term():
    term = request.form.get("term", "").strip()
    if term:
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


# ── Favoriten ────────────────────────────────────────────────

@bp.route("/listings/<int:listing_id>/favorite", methods=["POST"])
def toggle_favorite(listing_id):
    db.toggle_favorite(listing_id)
    return jsonify({"status": "ok"})


# ── Einstellungen ────────────────────────────────────────────

@bp.route("/settings")
def settings_page():
    settings = db.get_settings()
    return render_template("settings.html", s=settings)


@bp.route("/settings", methods=["POST"])
def save_settings():
    allowed_keys = {
        "kleinanzeigen_enabled", "kleinanzeigen_max_price",
        "kleinanzeigen_location", "kleinanzeigen_radius",
        "shpock_enabled", "shpock_max_price",
        "shpock_location", "shpock_radius",
        "facebook_enabled", "facebook_max_price", "facebook_location",
        "vinted_enabled", "vinted_max_price",
        "ebay_enabled", "ebay_max_price",
        "email_enabled", "email_smtp_server", "email_smtp_port",
        "email_sender", "email_password", "email_recipient",
        "crawler_interval", "crawler_max_results", "crawler_delay",
        "crawler_blacklist", "crawler_max_age_hours",
        "digest_enabled", "digest_time",
        "home_location",
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

    try:
        update_interval(int(data.get("crawler_interval", 60)))
    except (ValueError, TypeError):
        pass

    update_digest_schedule()

    flash("Einstellungen gespeichert.", "success")
    return redirect(url_for("main.settings_page"))


# ── Crawler-API ──────────────────────────────────────────────

@bp.route("/api/crawl", methods=["POST"])
def api_crawl():
    if is_running():
        return jsonify({"status": "already_running", "message": "Crawl läuft bereits."}), 409
    run_crawl_async()
    return jsonify({"status": "started", "message": "Crawl gestartet."})


@bp.route("/api/status")
def api_status():
    settings = db.get_settings()
    return jsonify({
        "crawl_status": settings.get("crawl_status", "idle"),
        "last_crawl": settings.get("last_crawl_end", ""),
        "next_crawl": get_next_run(),
        "last_found": settings.get("last_crawl_found", "0"),
        "total_listings": db.get_listing_count(),
        "is_running": is_running(),
    })


@bp.route("/api/listings")
def api_listings():
    term = request.args.get("term")
    platform = request.args.get("platform")
    try:
        limit = int(request.args.get("limit", 60))
        max_age = int(request.args.get("max_age", 0) or 0)
    except ValueError:
        return jsonify({"error": "limit und max_age müssen Ganzzahlen sein."}), 400
    only_fav = request.args.get("favorites") == "1"
    only_free = request.args.get("free") == "1"

    listings = db.get_listings(
        limit=limit, search_term=term, platform=platform,
        only_favorites=only_fav, only_free=only_free, max_age_hours=max_age,
    )
    return jsonify(listings)


@bp.route("/api/stats")
def api_stats():
    return jsonify(db.get_price_stats())


@bp.route("/api/log")
def api_log():
    from .logbuffer import get_lines
    return jsonify(get_lines())
