"""SQLite-Datenbankschicht für den Baby-Crawler."""

import os
import sqlite3
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_data_dir = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = _data_dir / "baby_crawler.db"

DEFAULT_SETTINGS: Dict[str, str] = {
    # Kleinanzeigen
    "kleinanzeigen_enabled": "1",
    "kleinanzeigen_max_price": "80",
    "kleinanzeigen_location": "München",
    "kleinanzeigen_radius": "30",
    # Shpock
    "shpock_enabled": "1",
    "shpock_max_price": "80",
    "shpock_location": "München",
    "shpock_radius": "30",
    # Fallback-Koordinaten für bestehende Installationen ohne shpock_location
    "shpock_latitude": "48.1351",
    "shpock_longitude": "11.5820",
    # Facebook
    "facebook_enabled": "0",
    "facebook_max_price": "80",
    "facebook_location": "München",
    # Vinted
    "vinted_enabled": "0",
    "vinted_max_price": "80",
    "vinted_location": "München",
    "vinted_radius": "30",
    # eBay
    "ebay_enabled": "0",
    "ebay_max_price": "80",
    "ebay_location": "München",
    "ebay_radius": "30",
    # E-Mail
    "email_enabled": "0",
    "email_smtp_server": "smtp.gmail.com",
    "email_smtp_port": "587",
    "email_sender": "",
    "email_password": "",
    "email_recipient": "",
    # Crawler
    "crawler_interval": "15",
    "crawler_max_results": "20",
    "crawler_delay": "2",
    "crawler_blacklist": "defekt\nbastler\nersatzteile\nbeschädigt\nkaputt\nschlachtfest",
    "crawler_max_age_hours": "0",   # 0 = kein Filter
    # Tages-Digest
    "digest_enabled": "0",
    "digest_time": "19:00",
    # Heimstandort für Entfernungsberechnung
    "home_location": "München",
    "home_latitude": "48.1351",
    "home_longitude": "11.5820",
    # Status
    "last_crawl_start": "",
    "last_crawl_end": "",
    "crawl_status": "idle",
    "last_crawl_found": "0",
}

DEFAULT_SEARCH_TERMS = [
    "kinderwagen", "babybett", "babyschale", "hochstuhl",
    "babywippe", "laufstall", "babytrage", "stillkissen",
]


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialisiert die Datenbank, erstellt Tabellen und führt Migrationen durch."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS search_terms (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            term       TEXT    NOT NULL UNIQUE,
            enabled    INTEGER NOT NULL DEFAULT 1,
            created_at TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS listings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id  TEXT    UNIQUE,
            platform    TEXT,
            title       TEXT,
            price       TEXT,
            location    TEXT,
            url         TEXT,
            image_url   TEXT,
            description TEXT,
            search_term TEXT,
            found_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS geocache (
            location_text TEXT PRIMARY KEY,
            lat           REAL,
            lon           REAL,
            cached_at     TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Migrationen für bestehende Datenbanken
    _migrate_settings_values(conn)
    _migrate_listings(conn)

    # Default-Settings nur eintragen wenn noch nicht vorhanden
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value)
        )

    # Default-Suchbegriffe nur beim ersten Start
    existing = conn.execute("SELECT COUNT(*) FROM search_terms").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO search_terms(term) VALUES (?)",
            [(t,) for t in DEFAULT_SEARCH_TERMS],
        )

    conn.commit()
    conn.close()
    logger.info(f"Datenbank initialisiert: {DB_PATH}")


def _migrate_settings_values(conn: sqlite3.Connection):
    """Aktualisiert veraltete Default-Werte in bestehenden Datenbanken."""
    # Standorte von altem Default "Dortmund" auf "München" migrieren
    location_keys = ["kleinanzeigen_location", "shpock_location", "facebook_location"]
    for key in location_keys:
        conn.execute("UPDATE settings SET value='München' WHERE key=? AND value='Dortmund'", (key,))
    # Fallback-Koordinaten ebenfalls aktualisieren
    coord_migrations = [
        ("shpock_latitude",  "51.5136", "48.1351"),
        ("shpock_longitude", "7.4653",  "11.5820"),
        ("home_latitude",    "51.5136", "48.1351"),
        ("home_longitude",   "7.4653",  "11.5820"),
    ]
    for key, old, new in coord_migrations:
        conn.execute("UPDATE settings SET value=? WHERE key=? AND value=?", (new, key, old))
    conn.commit()


def _migrate_listings(conn: sqlite3.Connection):
    """Ergänzt neue Spalten falls sie noch nicht existieren (für Updates)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    new_cols = [
        ("is_favorite", "INTEGER DEFAULT 0"),
        ("is_free",     "INTEGER DEFAULT 0"),
        ("distance_km", "REAL"),
    ]
    for col, definition in new_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {definition}")

    existing_geo = {row[1] for row in conn.execute("PRAGMA table_info(geocache)")}
    if "cached_at" not in existing_geo:
        conn.execute("ALTER TABLE geocache ADD COLUMN cached_at TEXT DEFAULT (datetime('now'))")

    conn.commit()


# ── Search Terms ────────────────────────────────────────────

def get_search_terms(enabled_only: bool = False) -> List[Dict]:
    conn = get_db()
    query = "SELECT * FROM search_terms"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY term ASC"
    rows = [dict(r) for r in conn.execute(query).fetchall()]
    conn.close()
    return rows


def add_search_term(term: str) -> bool:
    try:
        conn = get_db()
        conn.execute("INSERT INTO search_terms(term) VALUES (?)", (term.strip(),))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def delete_search_term(term_id: int):
    conn = get_db()
    conn.execute("DELETE FROM search_terms WHERE id = ?", (term_id,))
    conn.commit()
    conn.close()


def toggle_search_term(term_id: int):
    conn = get_db()
    conn.execute(
        "UPDATE search_terms SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id = ?",
        (term_id,),
    )
    conn.commit()
    conn.close()


# ── Settings ────────────────────────────────────────────────

def get_settings() -> Dict[str, str]:
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def save_settings(data: Dict[str, str]):
    conn = get_db()
    for key, value in data.items():
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
    conn.commit()
    conn.close()


# ── Listings ────────────────────────────────────────────────

def save_listing(listing) -> bool:
    """Gibt True zurück wenn die Anzeige neu war."""
    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO listings
               (listing_id,platform,title,price,location,url,image_url,
                description,search_term,is_free)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (listing.listing_id, listing.platform, listing.title, listing.price,
             listing.location, listing.url, listing.image_url, listing.description,
             listing.search_term, int(getattr(listing, "is_free", False))),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def update_listing_distance(listing_id: str, distance_km: float):
    conn = get_db()
    conn.execute(
        "UPDATE listings SET distance_km=? WHERE listing_id=?",
        (round(distance_km, 1), listing_id),
    )
    conn.commit()
    conn.close()


def toggle_favorite(listing_id: int):
    conn = get_db()
    conn.execute(
        "UPDATE listings SET is_favorite = CASE WHEN is_favorite=1 THEN 0 ELSE 1 END WHERE id=?",
        (listing_id,),
    )
    conn.commit()
    conn.close()


def get_listings(limit: int = 100, search_term: Optional[str] = None,
                 platform: Optional[str] = None, only_favorites: bool = False,
                 only_free: bool = False, max_age_hours: int = 0,
                 max_distance_km: Optional[float] = None) -> List[Dict]:
    conn = get_db()
    conditions: List[str] = []
    params: List[Any] = []

    if search_term:
        conditions.append("search_term = ?")
        params.append(search_term)
    if platform:
        conditions.append("platform = ?")
        params.append(platform)
    if only_favorites:
        conditions.append("is_favorite = 1")
    if only_free:
        conditions.append("is_free = 1")
    if max_age_hours and max_age_hours > 0:
        conditions.append("found_at >= datetime('now', ? || ' hours')")
        params.append(f"-{max_age_hours}")
    if max_distance_km is not None:
        # Anzeigen ohne berechnete Distanz werden nicht ausgefiltert
        conditions.append("(distance_km IS NULL OR distance_km <= ?)")
        params.append(max_distance_km)

    query = "SELECT * FROM listings"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY is_favorite DESC, is_free DESC, found_at DESC LIMIT ?"
    params.append(limit)

    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()
    return rows


def get_listing_count() -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    conn.close()
    return count


def get_listings_today() -> List[Dict]:
    """Alle Anzeigen von heute (für den Tages-Digest)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM listings WHERE found_at >= date('now') ORDER BY found_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_price_stats() -> List[Dict]:
    """Durchschnittspreis, Min, Max und Anzahl pro Suchbegriff."""
    conn = get_db()
    rows = conn.execute("""
        SELECT
            search_term,
            COUNT(*) as count,
            ROUND(AVG(CAST(REPLACE(REPLACE(price, ' €', ''), ',', '.') AS REAL)), 2) as avg_price,
            MIN(CAST(REPLACE(REPLACE(price, ' €', ''), ',', '.') AS REAL)) as min_price,
            MAX(CAST(REPLACE(REPLACE(price, ' €', ''), ',', '.') AS REAL)) as max_price,
            SUM(is_free) as free_count
        FROM listings
        WHERE price NOT IN ('k.A.', 'Preis nicht angegeben', '')
          AND CAST(REPLACE(REPLACE(price, ' €', ''), ',', '.') AS REAL) > 0
        GROUP BY search_term
        ORDER BY count DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_old_listings(days: int = 30):
    conn = get_db()
    conn.execute(
        "DELETE FROM listings WHERE is_favorite = 0 AND found_at < datetime('now', ? || ' days')",
        (f"-{days}",),
    )
    conn.commit()
    conn.close()


def clear_all_listings():
    """Löscht alle Anzeigen (außer Favoriten) und leert den Geocache."""
    conn = get_db()
    conn.execute("DELETE FROM listings WHERE is_favorite = 0")
    conn.execute("DELETE FROM geocache")
    conn.commit()
    conn.close()


# ── Geocache ────────────────────────────────────────────────

def get_geocache(location_text: str) -> Optional[tuple]:
    conn = get_db()
    row = conn.execute(
        "SELECT lat, lon FROM geocache WHERE location_text=?", (location_text,)
    ).fetchone()
    conn.close()
    return (row["lat"], row["lon"]) if row else None


def save_geocache(location_text: str, lat: float, lon: float):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO geocache(location_text, lat, lon) VALUES (?,?,?)",
        (location_text, lat, lon),
    )
    conn.commit()
    conn.close()
