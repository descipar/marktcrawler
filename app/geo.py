"""Geocoding (Nominatim/OSM) und Entfernungsberechnung (Haversine)."""

import logging
import math
import threading
import time
from typing import Optional

import requests

from . import database as db

logger = logging.getLogger(__name__)

_nominatim_lock = threading.Lock()
_last_nominatim_call: float = 0.0
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "baby-crawler/1.0 (private use)"}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Luftlinie in km zwischen zwei Koordinaten."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def geocode(location_text: str) -> Optional[tuple]:
    """
    Gibt (lat, lon) für einen Ortstext zurück.
    Nutzt DB-Cache, fragt bei Cache-Miss Nominatim an (max 1 Req/s).
    """
    if not location_text or len(location_text) < 3:
        return None

    # Cache-Lookup
    cached = db.get_geocache(location_text)
    if cached:
        return cached

    # Nominatim – Rate-Limit 1 req/s einhalten (thread-safe)
    global _last_nominatim_call
    with _nominatim_lock:
        wait = 1.1 - (time.time() - _last_nominatim_call)
        if wait > 0:
            time.sleep(wait)

        try:
            r = requests.get(
                NOMINATIM_URL,
                params={"q": location_text, "format": "json", "limit": 1, "countrycodes": "de,at,ch"},
                headers=NOMINATIM_HEADERS,
                timeout=10,
            )
            _last_nominatim_call = time.time()
            results = r.json()
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                db.save_geocache(location_text, lat, lon)
                logger.debug(f"Geocoded '{location_text}' → ({lat}, {lon})")
                return (lat, lon)
        except Exception as e:
            logger.debug(f"Geocoding fehlgeschlagen für '{location_text}': {e}")

    return None


def distance_to_home(location_text: str, settings: dict) -> Optional[float]:
    """
    Berechnet die Entfernung vom Heimstandort zu einem Ortstext.
    Liest den Heimstandort per Stadtname (home_location) oder als Fallback
    aus Koordinaten (home_latitude/home_longitude).
    """
    home_city = settings.get("home_location", "").strip()
    if home_city:
        home_coords = geocode(home_city)
        if not home_coords:
            logger.debug(f"Heimstandort '{home_city}' konnte nicht geocodiert werden.")
            return None
        home_lat, home_lon = home_coords
    else:
        try:
            home_lat = float(settings.get("home_latitude") or 0)
            home_lon = float(settings.get("home_longitude") or 0)
        except (TypeError, ValueError):
            return None
        if not home_lat or not home_lon:
            return None

    coords = geocode(location_text)
    if coords:
        return haversine(home_lat, home_lon, coords[0], coords[1])
    return None
