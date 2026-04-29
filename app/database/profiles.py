"""Profil-CRUD."""

from typing import Dict, List, Optional

from .core import _db


def get_profiles() -> List[Dict]:
    with _db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM profiles ORDER BY created_at"
        ).fetchall()]


def get_profile(profile_id: int) -> Optional[Dict]:
    with _db() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
    return dict(row) if row else None


def create_profile(name: str, emoji: str = "👤") -> int:
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO profiles (name, emoji) VALUES (?, ?)", (name.strip(), emoji.strip())
        )
        conn.commit()
        return cur.lastrowid


def update_profile(profile_id: int, name: str, emoji: str):
    with _db() as conn:
        conn.execute(
            "UPDATE profiles SET name=?, emoji=? WHERE id=?",
            (name.strip(), emoji.strip(), profile_id),
        )
        conn.commit()


def update_profile_notify(
    profile_id: int, email: str, notify_mode: str, digest_time: str,
    alert_interval_minutes: int = 15,
):
    _VALID_MODES = {"immediate", "digest_only", "both", "off"}
    if notify_mode not in _VALID_MODES:
        notify_mode = "immediate"
    interval = max(15, int(alert_interval_minutes or 15))
    with _db() as conn:
        conn.execute(
            "UPDATE profiles SET email=?, notify_mode=?, digest_time=?, alert_interval_minutes=? WHERE id=?",
            (email.strip() or None, notify_mode, digest_time or "19:00", interval, profile_id),
        )
        conn.commit()


def update_last_alert_sent(profile_id: int):
    with _db() as conn:
        conn.execute(
            "UPDATE profiles SET last_alert_sent_at=datetime('now') WHERE id=?",
            (profile_id,),
        )
        conn.commit()


def delete_profile(profile_id: int):
    with _db() as conn:
        conn.execute("DELETE FROM profiles WHERE id=?", (profile_id,))
        conn.commit()


def update_profile_last_seen(profile_id: int):
    with _db() as conn:
        conn.execute(
            "UPDATE profiles SET last_seen_at=datetime('now') WHERE id=?",
            (profile_id,),
        )
        conn.commit()
