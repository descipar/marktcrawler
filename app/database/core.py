"""DB-Verbindung, Initialisierung und Migrationen."""

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
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
    # Willhaben
    "willhaben_enabled": "0",
    "willhaben_max_price": "100",
    "willhaben_location": "München",
    "willhaben_radius": "50",
    "willhaben_paylivery_only": "1",  # nur Versand-Angebote (PayLivery)
    "willhaben_interval": "30",
    "willhaben_max_age_hours": "0",
    # markt.de
    "marktde_enabled": "0",
    "marktde_max_price": "100",
    "marktde_location": "München",
    "marktde_radius": "50",
    "marktde_interval": "60",
    "marktde_max_age_hours": "0",
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
    # Server-URL für E-Mail-Links (leer = automatische Erkennung)
    "server_url": "",
    # Sprachfilter
    "crawler_lang_filter_enabled": "0",
    "crawler_lang_filter_langs": "de",
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


def utcnow() -> datetime:
    """Aktuelle UTC-Zeit ohne Timezone-Info – konsistent mit SQLites datetime('now')."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _current_db_path() -> Path:
    """Liest DB_PATH aus dem Package-Namespace.

    Tests patchen `app.database.DB_PATH`. Diese Funktion respektiert das,
    indem sie den Wert zur Laufzeit auflöst statt beim Modulimport.
    """
    import sys
    pkg = sys.modules.get("app.database")
    return pkg.DB_PATH if pkg is not None else DB_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_current_db_path()), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def _db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialisiert die Datenbank, erstellt Tabellen und führt Migrationen durch."""
    path = _current_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
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

    _run_pending_migrations(conn)
    _ensure_indexes(conn)

    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value)
        )

    existing = conn.execute("SELECT COUNT(*) FROM search_terms").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO search_terms(term) VALUES (?)",
            [(t,) for t in DEFAULT_SEARCH_TERMS],
        )

    conn.commit()
    conn.close()
    logger.info(f"Datenbank initialisiert: {path}")


def _mig_settings_rename(conn: sqlite3.Connection):
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
    existing = {row[1] for row in conn.execute("PRAGMA table_info(search_terms)")}
    if "max_price" not in existing:
        conn.execute("ALTER TABLE search_terms ADD COLUMN max_price INTEGER NULL")


def _mig_backfill_notified_at(conn: sqlite3.Connection):
    """Markiert alle bestehenden Anzeigen als bereits benachrichtigt.

    Verhindert, dass beim ersten notify_pending()-Aufruf alle Altanzeigen
    als neu gelten und eine Massen-E-Mail auslösen.
    """
    conn.execute(
        "UPDATE listings SET notified_at=datetime('now') WHERE notified_at IS NULL"
    )


def _mig_rename_email_subjects(conn: sqlite3.Connection):
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


def _mig_image_url_large(conn: sqlite3.Connection):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "image_url_large" not in existing:
        conn.execute("ALTER TABLE listings ADD COLUMN image_url_large TEXT NOT NULL DEFAULT ''")


def _mig_create_log_tables(conn: sqlite3.Connection):
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
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "availability_checked_at" not in existing:
        conn.execute("ALTER TABLE listings ADD COLUMN availability_checked_at TEXT")


def _mig_profile_notify_fields(conn: sqlite3.Connection):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(profiles)")}
    if "email" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN email TEXT")
    if "notify_mode" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN notify_mode TEXT DEFAULT 'immediate'")
        conn.execute("UPDATE profiles SET notify_mode = 'immediate' WHERE notify_mode IS NULL")
    if "digest_time" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN digest_time TEXT DEFAULT '19:00'")
        conn.execute("UPDATE profiles SET digest_time = '19:00' WHERE digest_time IS NULL")


def _mig_profile_alert_interval(conn: sqlite3.Connection):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(profiles)")}
    if "alert_interval_minutes" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN alert_interval_minutes INTEGER DEFAULT 15")
    if "last_alert_sent_at" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN last_alert_sent_at TEXT")


def _mig_profile_quiet_hours(conn: sqlite3.Connection):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(profiles)")}
    if "quiet_start" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN quiet_start TEXT DEFAULT '20:00'")
    if "quiet_end" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN quiet_end TEXT DEFAULT '08:00'")


def _mig_cleanup_mismatched(conn: sqlite3.Connection):
    """Bereinigt Altanzeigen die nicht allen Wörtern ihres Suchbegriffs entsprechen.

    Einmalig nach Einführung des AND-Filters notwendig, damit historische
    OR-Treffer (z.B. 600 Vinted-Treffer für "body werder") entfernt werden.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "search_term" not in cols or "description" not in cols:
        return

    import re as _re

    def _ok(title: str, desc: str, term: str) -> bool:
        words = (term or "").lower().split()
        if len(words) <= 1:
            return True
        text = f"{title or ''} {desc or ''}".lower()
        return all(_re.search(r"\b" + _re.escape(w) + r"\b", text) for w in words)

    rows = conn.execute(
        "SELECT id, listing_id, title, description, search_term FROM listings"
    ).fetchall()
    mismatches = [r for r in rows if r["search_term"] and not _ok(r["title"], r["description"], r["search_term"])]
    if not mismatches:
        return
    listing_ids = [r["listing_id"] for r in mismatches]
    db_ids = [r["id"] for r in mismatches]
    conn.executemany(
        "INSERT OR IGNORE INTO dismissed_listings(listing_id, dismissed_at) VALUES(?, datetime('now'))",
        [(lid,) for lid in listing_ids],
    )
    placeholders = ",".join("?" * len(db_ids))
    conn.execute(f"DELETE FROM listings WHERE id IN ({placeholders})", db_ids)
    logger.info(f"Migration v9: {len(mismatches)} nicht passende Anzeigen bereinigt.")


def _mig_recalc_is_free(conn: sqlite3.Connection):
    """Berechnet is_free für alle Listings neu — korrigiert False-Positives
    durch das Willhaben-Preisformat '€ 9' (€ vor Zahl), das der alte
    _POSITIVE_PRICE_RE nicht erkannte."""
    import re as _re

    _free_price = _re.compile(
        r"^\s*(0\s*€?|0,00\s*€?|€\s*0([.,]0+)?|kostenlos|gratis|umsonst|zu\s+verschenken|verschenken|free)\s*$",
        _re.IGNORECASE,
    )
    _positive_price = _re.compile(r"\b[1-9]\d*([.,]\d+)?\s*€|€\s*[1-9]\d*([.,]\d+)?")
    _free_text = _re.compile(
        r"\b(zu\s+verschenken|verschenke|kostenlos|gratis|umsonst|zu\s+vergeben)\b",
        _re.IGNORECASE,
    )

    def _calc(price: str, title: str, desc: str) -> int:
        if _free_price.match(price):
            return 1
        if _positive_price.search(price):
            return 0
        if _free_text.search(title) or _free_text.search(desc):
            return 1
        return 0

    cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if not {"is_free", "description", "price", "title"}.issubset(cols):
        return  # Spalten noch nicht vorhanden — v2-Migration ergänzt sie mit Default 0
    rows = conn.execute("SELECT id, price, title, description FROM listings").fetchall()
    updates = [
        (_calc(r["price"] or "", r["title"] or "", r["description"] or ""), r["id"])
        for r in rows
    ]
    conn.executemany("UPDATE listings SET is_free = ? WHERE id = ?", updates)
    logger.info(f"Migration v13: is_free für {len(updates)} Anzeigen neu berechnet.")


_MIGRATIONS = [
    ("v1_settings_rename",          _mig_settings_rename),
    ("v2_listings_columns",         _mig_listings_columns),
    ("v3_search_terms_max_price",   _mig_search_terms_max_price),
    ("v4_backfill_notified_at",     _mig_backfill_notified_at),
    ("v5_rename_email_subjects",    _mig_rename_email_subjects),
    ("v6_image_url_large",          _mig_image_url_large),
    ("v7_create_log_tables",        _mig_create_log_tables),
    ("v8_availability_checked_at",  _mig_availability_checked_at),
    ("v9_cleanup_mismatched",       _mig_cleanup_mismatched),
    ("v10_profile_notify_fields",   _mig_profile_notify_fields),
    ("v11_profile_alert_interval",  _mig_profile_alert_interval),
    ("v12_profile_quiet_hours",     _mig_profile_quiet_hours),
    ("v13_recalc_is_free",          _mig_recalc_is_free),
]


def _run_pending_migrations(conn: sqlite3.Connection):
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


def _ensure_indexes(conn: sqlite3.Connection):
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
