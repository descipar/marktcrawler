"""SQLite-Datenbankschicht für den Baby-Crawler."""

import os
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

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
    "email_subject_alert": "🍼 Baby-Crawler: {n} neue Anzeige(n) gefunden!",
    "email_subject_digest": "🍼 Baby-Crawler Tages-Digest: {n} Anzeige(n) heute",
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
    "display_max_age_hours": "0",   # 0 = kein Filter
    # Tages-Digest
    "digest_enabled": "0",
    "digest_time": "19:00",
    # Heimstandort für Entfernungsberechnung
    "home_location": "München",
    "home_latitude": "48.1351",
    "home_longitude": "11.5820",
    # Verfügbarkeits-Check
    "availability_check_enabled": "1",
    "availability_check_interval_hours": "3",
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


@contextmanager
def _db() -> Generator[sqlite3.Connection, None, None]:
    """Context Manager für sichere DB-Verbindungen (auto-close auch bei Exceptions)."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


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
        CREATE TABLE IF NOT EXISTS dismissed_listings (
            listing_id   TEXT PRIMARY KEY,
            dismissed_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS profiles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            emoji        TEXT NOT NULL DEFAULT '👤',
            last_seen_at TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Migrationen für bestehende Datenbanken
    _migrate_settings_values(conn)
    _migrate_listings(conn)
    _migrate_search_terms(conn)

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
    # crawler_max_age_hours → display_max_age_hours
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) "
        "SELECT 'display_max_age_hours', value FROM settings WHERE key='crawler_max_age_hours'"
    )
    conn.execute("DELETE FROM settings WHERE key='crawler_max_age_hours'")
    conn.commit()


def _migrate_listings(conn: sqlite3.Connection):
    """Ergänzt neue Spalten falls sie noch nicht existieren (für Updates)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    new_cols = [
        ("is_favorite",         "INTEGER DEFAULT 0"),
        ("is_free",             "INTEGER DEFAULT 0"),
        ("distance_km",         "REAL"),
        ("notes",               "TEXT"),
        ("potential_duplicate", "TEXT"),
    ]
    for col, definition in new_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {definition}")

    existing_geo = {row[1] for row in conn.execute("PRAGMA table_info(geocache)")}
    if "cached_at" not in existing_geo:
        conn.execute("ALTER TABLE geocache ADD COLUMN cached_at TEXT DEFAULT (datetime('now'))")

    conn.commit()


def _migrate_search_terms(conn: sqlite3.Connection):
    """Ergänzt neue Spalten in search_terms falls sie noch nicht existieren."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(search_terms)")}
    if "max_price" not in existing:
        conn.execute("ALTER TABLE search_terms ADD COLUMN max_price INTEGER NULL")
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
        with _db() as conn:
            conn.execute("INSERT INTO search_terms(term) VALUES (?)", (term.strip(),))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def delete_search_term(term_id: int):
    with _db() as conn:
        row = conn.execute("SELECT term FROM search_terms WHERE id=?", (term_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM listings WHERE search_term=?", (row["term"],))
        conn.execute("DELETE FROM search_terms WHERE id=?", (term_id,))
        conn.commit()


def toggle_search_term(term_id: int):
    with _db() as conn:
        conn.execute(
            "UPDATE search_terms SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id = ?",
            (term_id,),
        )
        conn.commit()


def update_term_max_price(term_id: int, max_price: Optional[int]):
    with _db() as conn:
        conn.execute("UPDATE search_terms SET max_price=? WHERE id=?", (max_price, term_id))
        conn.commit()


# ── Settings ────────────────────────────────────────────────

def get_settings() -> Dict[str, str]:
    with _db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def get_setting(key: str, default: str = "") -> str:
    with _db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    with _db() as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


def save_settings(data: Dict[str, str]):
    with _db() as conn:
        for key, value in data.items():
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        conn.commit()


# ── Listings ────────────────────────────────────────────────

def is_dismissed(listing_id: str) -> bool:
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM dismissed_listings WHERE listing_id=?", (listing_id,)
        ).fetchone()
    return row is not None


def dismiss_listing(db_id: int):
    """Löscht eine Anzeige und merkt ihre listing_id dauerhaft als ausgeblendet."""
    with _db() as conn:
        row = conn.execute("SELECT listing_id FROM listings WHERE id=?", (db_id,)).fetchone()
        if row:
            conn.execute(
                "INSERT OR IGNORE INTO dismissed_listings(listing_id) VALUES(?)", (row["listing_id"],)
            )
            conn.execute("DELETE FROM listings WHERE id=?", (db_id,))
            conn.commit()


def save_listing(listing: "Listing") -> bool:
    """Gibt True zurück wenn die Anzeige neu war."""
    if is_dismissed(listing.listing_id):
        return False
    try:
        with _db() as conn:
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
        # Duplikat-Erkennung nach erfolgreichem INSERT
        dup_platform = find_duplicate_platform(listing.title, listing.platform)
        if dup_platform:
            with _db() as conn:
                conn.execute(
                    "UPDATE listings SET potential_duplicate=? WHERE listing_id=?",
                    (dup_platform, listing.listing_id)
                )
                conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def update_listing_distance(listing_id: str, distance_km: float):
    with _db() as conn:
        conn.execute(
            "UPDATE listings SET distance_km=? WHERE listing_id=?",
            (round(distance_km, 1), listing_id),
        )
        conn.commit()


def toggle_favorite(listing_id: int):
    with _db() as conn:
        conn.execute(
            "UPDATE listings SET is_favorite = CASE WHEN is_favorite=1 THEN 0 ELSE 1 END WHERE id=?",
            (listing_id,),
        )
        conn.commit()


def update_listing_note(db_id: int, note: str):
    with _db() as conn:
        conn.execute("UPDATE listings SET notes=? WHERE id=?", (note.strip() or None, db_id))
        conn.commit()


def find_duplicate_platform(title: str, platform: str) -> Optional[str]:
    """Sucht nach ähnlichem Listing auf anderer Plattform (letzte 30 Tage)."""
    normalized = title.lower().strip()[:50] if title else ""
    if len(normalized) < 5:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT platform FROM listings "
            "WHERE platform != ? "
            "AND found_at >= datetime('now', '-30 days') "
            "AND LOWER(SUBSTR(title,1,50)) = ? "
            "LIMIT 1",
            (platform, normalized),
        ).fetchone()
    return row["platform"] if row else None


def get_distinct_platforms() -> List[str]:
    """Gibt alle distinct Plattformen zurück, die in listings vorhanden sind."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT platform FROM listings ORDER BY platform"
        ).fetchall()
    return [r["platform"] for r in rows if r["platform"]]


def get_platform_counts() -> Dict[str, int]:
    """Gibt die Anzahl der Anzeigen pro Plattform zurück."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT platform, COUNT(*) as count FROM listings GROUP BY platform"
        ).fetchall()
    return {r["platform"]: r["count"] for r in rows if r["platform"]}


# GLOB '*[0-9]*' erkennt ob eine Ziffer vorhanden ist;
# ohne Ziffer (k.A., Kostenlos, …) → NULL damit NULLS LAST greift
_PRICE_EXPR = (
    "CASE WHEN price GLOB '*[0-9]*' "
    "THEN CAST(REPLACE(REPLACE(price,' €',''),',','.') AS REAL) "
    "ELSE NULL END"
)

_SORT_MAP: Dict[str, str] = {
    "date_desc":    f"is_free DESC, found_at DESC",
    "date_asc":     "found_at ASC",
    "price_asc":    f"({_PRICE_EXPR} IS NULL), {_PRICE_EXPR} ASC",
    "price_desc":   f"({_PRICE_EXPR} IS NULL), {_PRICE_EXPR} DESC",
    "distance_asc": "(distance_km IS NULL), distance_km ASC",
}


def get_listings(limit: int = 100, offset: int = 0,
                 search_terms: Optional[List[str]] = None,
                 platform: Optional[str] = None, only_favorites: bool = False,
                 only_free: bool = False, max_age_hours: int = 0,
                 max_distance_km: Optional[float] = None,
                 sort_by: str = "date_desc", exclude_text: Optional[str] = None) -> List[Dict]:
    conditions: List[str] = []
    params: List[Any] = []

    if search_terms:
        if len(search_terms) == 1:
            conditions.append("search_term = ?")
            params.append(search_terms[0])
        else:
            placeholders = ",".join("?" * len(search_terms))
            conditions.append(f"search_term IN ({placeholders})")
            params.extend(search_terms)
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
        conditions.append("(distance_km IS NULL OR distance_km <= ?)")
        params.append(max_distance_km)
    if exclude_text:
        like = f"%{exclude_text}%"
        conditions.append("title NOT LIKE ? AND COALESCE(description,'') NOT LIKE ?")
        params.extend([like, like])

    order = _SORT_MAP.get(sort_by, _SORT_MAP["date_desc"])
    query = "SELECT * FROM listings"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" ORDER BY is_favorite DESC, {order} LIMIT ? OFFSET ?"
    params.append(limit)
    params.append(offset)

    with _db() as conn:
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    return rows


def get_listing_count() -> int:
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]


def get_listings_today() -> List[Dict]:
    """Alle Anzeigen von heute (für den Tages-Digest)."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE found_at >= date('now') ORDER BY found_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_price_stats() -> List[Dict]:
    """Durchschnittspreis, Min, Max und Anzahl pro Suchbegriff."""
    with _db() as conn:
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
    return [dict(r) for r in rows]


def clear_old_listings(days: int = 30):
    with _db() as conn:
        conn.execute(
            "DELETE FROM listings WHERE is_favorite = 0 AND found_at < datetime('now', ? || ' days')",
            (f"-{days}",),
        )
        conn.commit()


def clear_listings_older_than(hours: int) -> int:
    """Löscht Anzeigen (außer Favoriten) die älter als `hours` Stunden sind.
    Trägt alle gelöschten listing_ids in dismissed_listings ein,
    damit sie beim nächsten Crawl nicht erneut gespeichert werden.
    Gibt die Anzahl der gelöschten Einträge zurück.
    """
    with _db() as conn:
        rows = conn.execute(
            "SELECT listing_id FROM listings "
            "WHERE is_favorite = 0 AND found_at < datetime('now', ? || ' hours')",
            (f"-{hours}",),
        ).fetchall()
        if not rows:
            return 0
        ids = [r["listing_id"] for r in rows]
        conn.executemany(
            "INSERT OR IGNORE INTO dismissed_listings(listing_id) VALUES(?)",
            [(lid,) for lid in ids],
        )
        conn.execute(
            "DELETE FROM listings WHERE is_favorite = 0 AND found_at < datetime('now', ? || ' hours')",
            (f"-{hours}",),
        )
        conn.commit()
    return len(ids)


def clear_all_listings():
    """Löscht alle Anzeigen (außer Favoriten) und leert den Geocache."""
    with _db() as conn:
        conn.execute("DELETE FROM listings WHERE is_favorite = 0")
        conn.execute("DELETE FROM geocache")
        conn.commit()


def get_all_listing_urls(min_age_minutes: int = 0) -> List[Dict]:
    """Gibt listing_id, url und title aller Anzeigen zurück (für Verfügbarkeits-Check).
    min_age_minutes: nur Anzeigen die mindestens so alt sind zurückgeben (0 = alle).
    """
    with _db() as conn:
        if min_age_minutes > 0:
            rows = conn.execute(
                "SELECT listing_id, url, title FROM listings "
                "WHERE found_at <= datetime('now', ? || ' minutes') "
                "ORDER BY found_at DESC",
                (f"-{min_age_minutes}",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT listing_id, url, title FROM listings ORDER BY found_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def delete_listing_by_listing_id(listing_id: str):
    """Löscht eine Anzeige anhand ihrer listing_id – auch wenn sie Favorit ist."""
    with _db() as conn:
        conn.execute("DELETE FROM listings WHERE listing_id = ?", (listing_id,))
        conn.commit()


# ── Geocache ────────────────────────────────────────────────

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


# ── Profile ──────────────────────────────────────────────────

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
