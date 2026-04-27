"""Geocache-CRUD."""

from typing import Optional

from .core import _db


def get_geocache(location_text: str) -> Optional[tuple]:
    with _db() as conn:
        row = conn.execute(
            "SELECT lat, lon FROM geocache WHERE location_text=?", (location_text,)
        ).fetchone()
    return (row["lat"], row["lon"]) if row else None


def save_geocache(location_text: str, lat: float, lon: float):
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO geocache(location_text, lat, lon, cached_at) VALUES (?,?,?,datetime('now'))",
            (location_text, lat, lon),
        )
        conn.commit()
