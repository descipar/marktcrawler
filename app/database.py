"""SQLite-Datenbankschicht für den Marktcrawler."""

import os
import sqlite3
import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta
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
    "kleinanzeigen_max_age_hours": "0",
    # Shpock
    "shpock_enabled": "1",
    "shpock_max_price": "80",
    "shpock_location": "München",
    "shpock_radius": "30",
    "shpock_max_age_hours": "0",
    # Fallback-Koordinaten für bestehende Installationen ohne shpock_location
    "shpock_latitude": "48.1351",
    "shpock_longitude": "11.5820",
    # Facebook
    "facebook_enabled": "0",
    "facebook_max_price": "80",
    "facebook_location": "München",
    "facebook_max_age_hours": "0",
    # Vinted
    "vinted_enabled": "0",
    "vinted_max_price": "80",
    "vinted_location": "München",
    "vinted_radius": "30",
    "vinted_max_age_hours": "48",  # Vinted hat viele ältere Anzeigen
    # eBay
    "ebay_enabled": "0",
    "ebay_max_price": "80",
    "ebay_location": "München",
    "ebay_radius": "30",
    "ebay_max_age_hours": "0",
    # E-Mail
    "email_enabled": "0",
    "email_subject_alert": "🔍 Marktcrawler: {n} neue Anzeige(n) gefunden!",
    "email_subject_digest": "🔍 Marktcrawler Tages-Digest: {n} Anzeige(n) heute",
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
    "availability_check_workers": "5",
    "availability_recheck_hours": "48",  # Anzeige frühestens nach N Stunden erneut prüfen
    # KI-Assistent
    "ai_enabled": "0",
    "ai_api_key": "",
    "ai_model": "claude-haiku-4-5-20251001",
    "ai_base_url": "",
    "ai_prompt_hints": "",
    # Status
    "last_crawl_start": "",
    "last_crawl_end": "",
    "crawl_status": "idle",
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
        CREATE TABLE IF NOT EXISTS crawl_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            platform    TEXT NOT NULL,
            started_at  TEXT NOT NULL,
            ended_at    TEXT NOT NULL,
            duration_s  REAL NOT NULL DEFAULT 0,
            found_count INTEGER NOT NULL DEFAULT 0,
            term_count  INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS notification_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
            type            TEXT NOT NULL,
            listing_count   INTEGER NOT NULL DEFAULT 0,
            recipient_count INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.commit()

    # Migrationen für bestehende Datenbanken (müssen vor Indizes laufen)
    _run_pending_migrations(conn)
    _ensure_indexes(conn)

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


def _mig_settings_rename(conn: sqlite3.Connection):
    """Aktualisiert veraltete Default-Werte (Dortmund→München, alter Spaltenname)."""
    for key in ["kleinanzeigen_location", "shpock_location", "facebook_location"]:
        conn.execute("UPDATE settings SET value='München' WHERE key=? AND value='Dortmund'", (key,))
    for key, old, new in [
        ("shpock_latitude",  "51.5136", "48.1351"),
        ("shpock_longitude", "7.4653",  "11.5820"),
        ("home_latitude",    "51.5136", "48.1351"),
        ("home_longitude",   "7.4653",  "11.5820"),
    ]:
        conn.execute("UPDATE settings SET value=? WHERE key=? AND value=?", (new, key, old))
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) "
        "SELECT 'display_max_age_hours', value FROM settings WHERE key='crawler_max_age_hours'"
    )
    conn.execute("DELETE FROM settings WHERE key='crawler_max_age_hours'")


def _mig_listings_columns(conn: sqlite3.Connection):
    """Ergänzt neue Listings-Spalten für ältere Datenbanken."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    for col, definition in [
        ("is_favorite",         "INTEGER DEFAULT 0"),
        ("is_free",             "INTEGER DEFAULT 0"),
        ("distance_km",         "REAL"),
        ("notes",               "TEXT"),
        ("potential_duplicate", "TEXT"),
        ("notified_at",         "TEXT"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {definition}")

    existing_geo = {row[1] for row in conn.execute("PRAGMA table_info(geocache)")}
    if "cached_at" not in existing_geo:
        conn.execute("ALTER TABLE geocache ADD COLUMN cached_at TEXT DEFAULT (datetime('now'))")


def _mig_search_terms_max_price(conn: sqlite3.Connection):
    """Ergänzt max_price-Spalte in search_terms."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(search_terms)")}
    if "max_price" not in existing:
        conn.execute("ALTER TABLE search_terms ADD COLUMN max_price INTEGER NULL")


def _mig_backfill_notified_at(conn: sqlite3.Connection):
    """Markiert alle bestehenden Anzeigen als bereits benachrichtigt.

    Ohne diesen Schritt würden alle Einträge, die vor Einführung der
    notified_at-Spalte existierten, beim nächsten notify_pending()-Aufruf
    als "neu unbenachrichtigt" gelten und eine Massen-E-Mail auslösen.
    """
    conn.execute(
        "UPDATE listings SET notified_at=datetime('now') WHERE notified_at IS NULL"
    )


def _ensure_indexes(conn: sqlite3.Connection):
    """Erstellt Performance-Indizes nur für vorhandene Spalten (idempotent)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    for idx_name, col in [
        ("idx_listings_platform",    "platform"),
        ("idx_listings_search_term", "search_term"),
        ("idx_listings_found_at",    "found_at"),
        ("idx_listings_is_favorite", "is_favorite"),
        ("idx_listings_notified_at", "notified_at"),
    ]:
        if col in existing:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON listings({col})")
    if {"platform", "found_at"} <= existing:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_listings_plat_found ON listings(platform, found_at)"
        )
    conn.commit()


def _mig_create_log_tables(conn: sqlite3.Connection):
    """Erstellt crawl_log und notification_log für Statistik-Tracking."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crawl_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            platform    TEXT NOT NULL,
            started_at  TEXT NOT NULL,
            ended_at    TEXT NOT NULL,
            duration_s  REAL NOT NULL DEFAULT 0,
            found_count INTEGER NOT NULL DEFAULT 0,
            term_count  INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
            type            TEXT NOT NULL,
            listing_count   INTEGER NOT NULL DEFAULT 0,
            recipient_count INTEGER NOT NULL DEFAULT 0
        )
    """)


def _mig_availability_checked_at(conn: sqlite3.Connection):
    """Ergänzt availability_checked_at für selektives Re-Check-Throttling."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "availability_checked_at" not in existing:
        conn.execute("ALTER TABLE listings ADD COLUMN availability_checked_at TEXT")


def _mig_image_url_large(conn: sqlite3.Connection):
    """Ergänzt image_url_large-Spalte für hochauflösende Bilder im Modal."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "image_url_large" not in existing:
        conn.execute("ALTER TABLE listings ADD COLUMN image_url_large TEXT NOT NULL DEFAULT ''")


def _mig_rename_email_subjects(conn: sqlite3.Connection):
    """Aktualisiert die E-Mail-Betreff-Defaults von Baby-Crawler auf Marktcrawler.

    Nur wenn der Wert noch dem alten Default entspricht – benutzerdefinierte
    Betreffs werden nicht überschrieben.
    """
    conn.execute(
        "UPDATE settings SET value=? WHERE key='email_subject_alert' AND value=?",
        ("🔍 Marktcrawler: {n} neue Anzeige(n) gefunden!",
         "🍼 Baby-Crawler: {n} neue Anzeige(n) gefunden!"),
    )
    conn.execute(
        "UPDATE settings SET value=? WHERE key='email_subject_digest' AND value=?",
        ("🔍 Marktcrawler Tages-Digest: {n} Anzeige(n) heute",
         "🍼 Baby-Crawler Tages-Digest: {n} Anzeige(n) heute"),
    )


_MIGRATIONS = [
    ("v1_settings_rename",          _mig_settings_rename),
    ("v2_listings_columns",         _mig_listings_columns),
    ("v3_search_terms_max_price",   _mig_search_terms_max_price),
    ("v4_backfill_notified_at",     _mig_backfill_notified_at),
    ("v5_rename_email_subjects",    _mig_rename_email_subjects),
    ("v6_image_url_large",          _mig_image_url_large),
    ("v7_create_log_tables",        _mig_create_log_tables),
    ("v8_availability_checked_at",  _mig_availability_checked_at),
]


def _run_pending_migrations(conn: sqlite3.Connection):
    """Führt noch nicht angewandte Migrationen aus und protokolliert sie."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            name       TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    """)
    applied = {row[0] for row in conn.execute("SELECT name FROM _migrations").fetchall()}
    for name, fn in _MIGRATIONS:
        if name not in applied:
            fn(conn)
            conn.execute("INSERT INTO _migrations(name) VALUES(?)", (name,))
            logger.info(f"Migration angewendet: {name}")
    conn.commit()


# ── Search Terms ────────────────────────────────────────────

def get_search_terms(enabled_only: bool = False) -> List[Dict]:
    query = "SELECT * FROM search_terms"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY term ASC"
    with _db() as conn:
        return [dict(r) for r in conn.execute(query).fetchall()]


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
                   (listing_id,platform,title,price,location,url,image_url,image_url_large,
                    description,search_term,is_free)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (listing.listing_id, listing.platform, listing.title, listing.price,
                 listing.location, listing.url, listing.image_url,
                 getattr(listing, "image_url_large", ""),
                 listing.description, listing.search_term,
                 int(getattr(listing, "is_free", False))),
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
    # Strip ` €`, then thousands-separator `.`, then convert decimal `,` → `.`
    # e.g. "1.250,50 €" → "125050" ... wait, strip `.` first → "1250,50" → "1250.50" ✓
    "THEN CAST(REPLACE(REPLACE(REPLACE(price,' €',''),'.',''),',','.') AS REAL) "
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
                 platform_max_ages: Optional[Dict[str, int]] = None,
                 max_distance_km: Optional[float] = None,
                 sort_by: str = "date_desc", exclude_text: Optional[str] = None,
                 since_datetime: Optional[str] = None) -> List[Dict]:
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
        # Global override: one cutoff for all platforms
        conditions.append("found_at >= datetime('now', ? || ' hours')")
        params.append(f"-{max_age_hours}")
    elif platform_max_ages:
        # Per-platform cutoffs: exclude listings older than platform-specific limit
        exclusions = [(p, h) for p, h in platform_max_ages.items() if h and h > 0]
        if exclusions:
            parts = ["(platform = ? AND found_at < datetime('now', ? || ' hours'))"] * len(exclusions)
            conditions.append("NOT (" + " OR ".join(parts) + ")")
            for p, h in exclusions:
                params.extend([p, f"-{h}"])
    if max_distance_km is not None:
        conditions.append("(distance_km IS NULL OR distance_km <= ?)")
        params.append(max_distance_km)
    if exclude_text:
        like = f"%{exclude_text}%"
        conditions.append("title NOT LIKE ? AND COALESCE(description,'') NOT LIKE ?")
        params.extend([like, like])
    if since_datetime:
        conditions.append("found_at > ?")
        params.append(since_datetime)

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


def get_listing_by_id(db_id: int) -> Optional[Dict]:
    """Einzelne Anzeige per DB-Primary-Key."""
    with _db() as conn:
        row = conn.execute("SELECT * FROM listings WHERE id=?", (db_id,)).fetchone()
    return dict(row) if row else None


def get_unnotified_listings() -> List[Dict]:
    """Alle Anzeigen ohne Benachrichtigung, sortiert nach Plattform und Suchbegriff."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE notified_at IS NULL "
            "ORDER BY platform, search_term, found_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def mark_listings_notified(listing_ids: List[str]):
    """Setzt notified_at für die angegebenen listing_ids (in Chunks à 500)."""
    if not listing_ids:
        return
    with _db() as conn:
        for i in range(0, len(listing_ids), 500):
            chunk = listing_ids[i:i + 500]
            placeholders = ",".join("?" * len(chunk))
            conn.execute(
                f"UPDATE listings SET notified_at=datetime('now') WHERE listing_id IN ({placeholders})",
                chunk,
            )
        conn.commit()


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


def get_all_listing_urls(min_age_minutes: int = 0,
                         recheck_hours: int = 0) -> List[Dict]:
    """Gibt listing_id, url und title der zu prüfenden Anzeigen zurück.

    min_age_minutes: Anzeigen jünger als N Minuten überspringen.
    recheck_hours:   Anzeigen überspringen die in den letzten N Stunden bereits
                     geprüft wurden (0 = alle prüfen).
    """
    conditions = []
    params: List[Any] = []
    if min_age_minutes > 0:
        conditions.append("found_at <= datetime('now', ? || ' minutes')")
        params.append(f"-{min_age_minutes}")
    if recheck_hours > 0:
        conditions.append(
            "(availability_checked_at IS NULL "
            "OR availability_checked_at < datetime('now', ? || ' hours'))"
        )
        params.append(f"-{recheck_hours}")
    query = "SELECT listing_id, url, title FROM listings"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY COALESCE(availability_checked_at, '1970-01-01') ASC"
    with _db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def mark_listings_availability_checked(listing_ids: List[str]):
    """Setzt availability_checked_at = NOW() für die gegebenen listing_ids (Chunks à 500)."""
    if not listing_ids:
        return
    now = datetime.now().isoformat(timespec="seconds")
    with _db() as conn:
        for i in range(0, len(listing_ids), 500):
            chunk = listing_ids[i:i + 500]
            placeholders = ",".join("?" * len(chunk))
            conn.execute(
                f"UPDATE listings SET availability_checked_at = ? WHERE listing_id IN ({placeholders})",
                [now, *chunk],
            )
        conn.commit()


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


# ── Crawl- und Benachrichtigungs-Logging ────────────────────

def log_crawl_run(platform: str, started_at: str, ended_at: str,
                  duration_s: float, found_count: int, term_count: int):
    """Protokolliert einen abgeschlossenen Crawl-Lauf."""
    with _db() as conn:
        conn.execute(
            "INSERT INTO crawl_log (platform, started_at, ended_at, duration_s, found_count, term_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (platform, started_at, ended_at, duration_s, found_count, term_count),
        )
        conn.commit()


def log_notification(notif_type: str, listing_count: int, recipient_count: int):
    """Protokolliert einen E-Mail-Versand (Alert oder Digest)."""
    with _db() as conn:
        conn.execute(
            "INSERT INTO notification_log (type, listing_count, recipient_count) VALUES (?, ?, ?)",
            (notif_type, listing_count, recipient_count),
        )
        conn.commit()


# ── System-Statistiken ───────────────────────────────────────

def get_system_stats() -> Dict:
    """Liefert alle Statistiken für die Info-Seite."""
    try:
        db_size_bytes = os.path.getsize(str(DB_PATH))
    except OSError:
        db_size_bytes = 0

    try:
        st = os.statvfs(str(DB_PATH.parent))
        disk_free_bytes = st.f_frsize * st.f_bavail
        disk_total_bytes = st.f_frsize * st.f_blocks
    except (AttributeError, OSError):
        disk_free_bytes = 0
        disk_total_bytes = 0

    with _db() as conn:
        def _n(q, *p):
            row = conn.execute(q, p).fetchone()
            return (row[0] or 0) if row else 0

        total          = _n("SELECT COUNT(*) FROM listings")
        favorites      = _n("SELECT COUNT(*) FROM listings WHERE is_favorite=1")
        free_count     = _n("SELECT COUNT(*) FROM listings WHERE is_free=1")
        with_notes     = _n("SELECT COUNT(*) FROM listings WHERE notes IS NOT NULL AND notes!=''")
        no_image       = _n("SELECT COUNT(*) FROM listings WHERE image_url IS NULL OR image_url=''")
        duplicates     = _n("SELECT COUNT(*) FROM listings WHERE potential_duplicate IS NOT NULL")
        dismissed      = _n("SELECT COUNT(*) FROM dismissed_listings")
        today_count    = _n("SELECT COUNT(*) FROM listings WHERE found_at >= date('now')")
        last7_count    = _n("SELECT COUNT(*) FROM listings WHERE found_at >= datetime('now', '-7 days')")
        geocache_count = _n("SELECT COUNT(*) FROM geocache")
        term_total     = _n("SELECT COUNT(*) FROM search_terms")
        term_active    = _n("SELECT COUNT(*) FROM search_terms WHERE enabled=1")
        profile_count  = _n("SELECT COUNT(*) FROM profiles")
        total_crawls   = _n("SELECT COUNT(*) FROM crawl_log")
        total_notifs   = _n("SELECT COUNT(*) FROM notification_log")

        plat_rows = conn.execute(
            "SELECT platform, COUNT(*) as cnt FROM listings GROUP BY platform ORDER BY cnt DESC"
        ).fetchall()
        platforms = [{"platform": r["platform"], "count": r["cnt"]} for r in plat_rows]

        top_term_rows = conn.execute(
            "SELECT search_term, COUNT(*) as cnt FROM listings "
            "GROUP BY search_term ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        top_terms = [{"term": r["search_term"], "count": r["cnt"]} for r in top_term_rows]

        today_date = date.today()
        all_days = [(today_date - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        raw_daily = conn.execute(
            "SELECT date(found_at) as day, COUNT(*) as cnt FROM listings "
            "WHERE found_at >= date('now', '-6 days') GROUP BY day"
        ).fetchall()
        daily_map = {r["day"]: r["cnt"] for r in raw_daily}
        daily = [{"day": d, "count": daily_map.get(d, 0)} for d in all_days]

        price_row = conn.execute(
            "SELECT AVG(CAST(REPLACE(REPLACE(price,' €',''),',','.') AS REAL)) as avg_p, "
            "MIN(CAST(REPLACE(REPLACE(price,' €',''),',','.') AS REAL)) as min_p, "
            "MAX(CAST(REPLACE(REPLACE(price,' €',''),',','.') AS REAL)) as max_p "
            "FROM listings WHERE price GLOB '*[0-9]*' AND is_free=0"
        ).fetchone()
        price_unknown = _n("SELECT COUNT(*) FROM listings WHERE price NOT GLOB '*[0-9]*'")

        crawl_rows = conn.execute(
            "SELECT platform, COUNT(*) as runs, AVG(duration_s) as avg_dur, "
            "MAX(ended_at) as last_run, SUM(found_count) as total_found "
            "FROM crawl_log GROUP BY platform ORDER BY platform"
        ).fetchall()
        crawl_stats = [
            {
                "platform": r["platform"],
                "runs": r["runs"],
                "avg_duration_s": round(r["avg_dur"], 1) if r["avg_dur"] else 0,
                "last_run": r["last_run"] or "",
                "total_found": r["total_found"] or 0,
            }
            for r in crawl_rows
        ]

        notif_rows = conn.execute(
            "SELECT type, COUNT(*) as total, MAX(sent_at) as last_sent, "
            "AVG(listing_count) as avg_listings "
            "FROM notification_log GROUP BY type ORDER BY type"
        ).fetchall()
        notif_stats = [
            {
                "type": r["type"],
                "total": r["total"],
                "last_sent": r["last_sent"] or "",
                "avg_listings": round(r["avg_listings"], 1) if r["avg_listings"] else 0,
            }
            for r in notif_rows
        ]

        migration_rows = conn.execute(
            "SELECT name, applied_at FROM _migrations ORDER BY applied_at"
        ).fetchall()
        migrations = [{"name": r["name"], "applied_at": r["applied_at"]} for r in migration_rows]

    return {
        "db_size_bytes":      db_size_bytes,
        "db_size_mb":         round(db_size_bytes / (1024 * 1024), 2),
        "disk_free_bytes":    disk_free_bytes,
        "disk_free_gb":       round(disk_free_bytes / (1024 ** 3), 2),
        "disk_total_bytes":   disk_total_bytes,
        "disk_total_gb":      round(disk_total_bytes / (1024 ** 3), 2),
        "disk_used_pct":      round((1 - disk_free_bytes / disk_total_bytes) * 100, 1)
                              if disk_total_bytes else 0,
        "geocache_count":     geocache_count,
        "listings_total":     total,
        "listings_today":     today_count,
        "listings_last_7d":   last7_count,
        "listings_favorites": favorites,
        "listings_free":      free_count,
        "listings_with_notes": with_notes,
        "listings_no_image":  no_image,
        "listings_duplicates": duplicates,
        "listings_dismissed": dismissed,
        "platforms":          platforms,
        "top_terms":          top_terms,
        "daily_counts":       daily,
        "daily_max":          max((d["count"] for d in daily), default=0) or 1,
        "price_avg":          round(price_row["avg_p"], 2) if price_row and price_row["avg_p"] else None,
        "price_min":          round(price_row["min_p"], 2) if price_row and price_row["min_p"] else None,
        "price_max":          round(price_row["max_p"], 2) if price_row and price_row["max_p"] else None,
        "price_unknown_count": price_unknown,
        "crawl_stats":        crawl_stats,
        "total_crawl_runs":   total_crawls,
        "notif_stats":        notif_stats,
        "total_notifications": total_notifs,
        "search_term_count":  term_total,
        "active_term_count":  term_active,
        "profile_count":      profile_count,
        "migrations":         migrations,
    }
