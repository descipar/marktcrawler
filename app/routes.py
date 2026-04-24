"""Flask-Routen: Dashboard, Einstellungen, REST-API."""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash

from . import database as db
from .crawler import run_crawl_async, is_running
from .scheduler import get_next_run, update_interval

bp = Blueprint("main", __name__)


# ── Dashboard ────────────────────────────────────────────────

@bp.route("/")
def index():
    search_terms = db.get_search_terms()
    listings = db.get_listings(limit=60)
    settings = db.get_settings()
    stats = {
        "total_listings": db.get_listing_count(),
        "last_crawl": settings.get("last_crawl_end", "") or "Noch kein Lauf",
        "next_crawl": get_next_run(),
        "crawl_status": settings.get("crawl_status", "idle"),
        "last_found": settings.get("last_crawl_found", "0"),
    }
    return render_template("index.html",
                           search_terms=search_terms,
                           listings=listings,
                           stats=stats)


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


# ── Einstellungen ────────────────────────────────────────────

@bp.route("/settings")
def settings_page():
    settings = db.get_settings()
    return render_template("settings.html", s=settings)


@bp.route("/settings", methods=["POST"])
def save_settings():
    allowed_keys = {
        "kleinanzeigen_enabled", "kleinanzeigen_max_price", "kleinanzeigen_location", "kleinanzeigen_radius",
        "shpock_enabled", "shpock_max_price", "shpock_latitude", "shpock_longitude", "shpock_radius",
        "facebook_enabled", "facebook_max_price", "facebook_location",
        "email_enabled", "email_smtp_server", "email_smtp_port",
        "email_sender", "email_password", "email_recipient",
        "crawler_interval", "crawler_max_results", "crawler_delay",
    }
    data = {}
    for key in allowed_keys:
        # Checkboxen senden nur Wert wenn angehakt → fehlender Key = 0
        if key.endswith("_enabled"):
            data[key] = "1" if request.form.get(key) else "0"
        else:
            val = request.form.get(key, "")
            if val is not None:
                data[key] = val

    db.save_settings(data)

    # Scheduler-Intervall live aktualisieren
    try:
        new_interval = int(data.get("crawler_interval", 60))
        update_interval(new_interval)
    except (ValueError, TypeError):
        pass

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
    limit = int(request.args.get("limit", 60))
    listings = db.get_listings(limit=limit, search_term=term, platform=platform)
    return jsonify(listings)
