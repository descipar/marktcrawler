"""SQLite-Datenbankschicht für den Baby-Crawler."""

import sqlite3
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("/data/baby_crawler.db")

DEFAULT_SETTINGS: Dict[str, str] = {
    # Kleinanzeigen
    "kleinanzeigen_enabled": "1",
    "kleinanzeigen_max_price": "80",
    "kleinanzeigen_location": "Dortmund",
    "kleinanzeigen_radius": "30",
    # Shpock
    "shpock_enabled": "1",
    "shpock_max_price": "80",
    "shpock_latitude": "51.5136",
    "shpock_longitude": "7.4653",
    "shpock_radius": "30",
    # Facebook
    "facebook_enabled": "0",
    "facebook_max_price": "80",
    "facebook_location": "Dortmund",
    # E-Mail
    "email_enabled": "0",
    "email_smtp_server": "smtp.gmail.com",
    "email_smtp_port": "587",
    "email_sender": "",
    "email_password": "",
    "email_recipient": "",
    # Crawler
    "crawler_interval": "60",
    "crawler_max_results": "20",
    "crawler_delay": "2",
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
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialisiert die Datenbank und füllt Default-Werte."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS search_terms (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            term      TEXT    NOT NULL UNIQUE,
            enabled   INTEGER NOT NULL DEFAULT 1,
            created_at TEXT   DEFAULT (datetime('now'))
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
    """)
    conn.commit()

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
               (listing_id,platform,title,price,location,url,image_url,description,search_term)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (listing.listing_id, listing.platform, listing.title, listing.price,
             listing.location, listing.url, listing.image_url, listing.description,
             listing.search_term),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False  # bereits vorhanden


def get_listings(limit: int = 100, search_term: Optional[str] = None,
                 platform: Optional[str] = None) -> List[Dict]:
    conn = get_db()
    query = "SELECT * FROM listings"
    params: List[Any] = []
    conditions = []
    if search_term:
        conditions.append("search_term = ?")
        params.append(search_term)
    if platform:
        conditions.append("platform = ?")
        params.append(platform)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY found_at DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()
    return rows


def get_listing_count() -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    conn.close()
    return count


def clear_old_listings(days: int = 30):
    conn = get_db()
    conn.execute(
        "DELETE FROM listings WHERE found_at < datetime('now', ? || ' days')",
        (f"-{days}",),
    )
    conn.commit()
    conn.close()
