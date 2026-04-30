"""Profil-Routen (/profiles/*)."""

from flask import request, jsonify, redirect, url_for, flash, session

from . import bp
from .. import database as db


@bp.route("/profiles/select")
def profiles_select():
    profiles = db.get_profiles()
    if not profiles:
        return redirect(url_for("main.index"))
    from flask import render_template
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


@bp.route("/profiles/<int:profile_id>/notify", methods=["POST"])
def update_profile_notify_route(profile_id):
    data = request.json or {}
    email = data.get("email", "").strip()
    notify_mode = data.get("notify_mode", "immediate")
    digest_time = data.get("digest_time", "19:00")
    alert_interval_minutes = int(data.get("alert_interval_minutes") or 15)
    quiet_start = data.get("quiet_start", "20:00")
    quiet_end = data.get("quiet_end", "08:00")
    db.update_profile_notify(
        profile_id, email, notify_mode, digest_time, alert_interval_minutes,
        quiet_start, quiet_end,
    )
    try:
        from ..scheduler import update_profile_digest_schedules
        update_profile_digest_schedules()
    except Exception:
        pass
    return jsonify({"status": "ok"})


@bp.route("/profiles/<int:profile_id>/delete", methods=["POST"])
def delete_profile_route(profile_id):
    if session.get("profile_id") == profile_id:
        for key in ("profile_id", "profile_name", "profile_emoji", "profile_last_seen"):
            session.pop(key, None)
    db.delete_profile(profile_id)
    return jsonify({"status": "ok"})
