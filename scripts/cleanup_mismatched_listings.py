"""Prüft bestehende Anzeigen gegen ihre gespeicherten Suchbegriffe (AND-Logik).

Anzeigen, deren Titel + Beschreibung nicht alle Wörter des zugehörigen
Suchbegriffs enthalten, wurden vor Einführung des AND-Filters gespeichert
und werden optional gelöscht.

Aufruf:
    python scripts/cleanup_mismatched_listings.py           # nur Bericht
    python scripts/cleanup_mismatched_listings.py --delete  # löschen
    DATA_DIR=./data python scripts/cleanup_mismatched_listings.py --delete
"""

import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path

# Projekt-Root ins sys.path damit dotenv + app imports funktionieren
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "baby_crawler.db"


def _matches_all_words(title: str, description: str, term: str) -> bool:
    words = term.lower().split()
    if len(words) <= 1:
        return True
    text = f"{title or ''} {description or ''}".lower()
    return all(bool(re.search(r"\b" + re.escape(w) + r"\b", text)) for w in words)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--delete", action="store_true", help="Nicht passende Anzeigen löschen")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Datenbank nicht gefunden: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, listing_id, title, description, search_term, platform FROM listings"
    ).fetchall()

    mismatches = [
        r for r in rows
        if r["search_term"] and not _matches_all_words(r["title"], r["description"], r["search_term"])
    ]

    total = len(rows)
    bad = len(mismatches)
    print(f"Gesamt: {total} Anzeigen  |  Nicht passend: {bad}")

    if not mismatches:
        print("Alles in Ordnung – keine Anzeigen zu bereinigen.")
        conn.close()
        return

    # Gruppenübersicht nach Suchbegriff
    from collections import defaultdict
    by_term: dict = defaultdict(list)
    for r in mismatches:
        by_term[r["search_term"]].append(r)

    print()
    for term, listings in sorted(by_term.items()):
        print(f"  [{term}]  →  {len(listings)} nicht passend")
        for r in listings[:5]:
            title_preview = (r["title"] or "")[:70]
            print(f"      • [{r['platform']}] {title_preview}")
        if len(listings) > 5:
            print(f"      … und {len(listings) - 5} weitere")

    if not args.delete:
        print(f"\nHinweis: Zum Löschen --delete übergeben.")
        conn.close()
        return

    ids = [r["id"] for r in mismatches]
    listing_ids = [r["listing_id"] for r in mismatches]

    # Nicht passende Anzeigen in dismissed_listings eintragen damit sie beim
    # nächsten Crawl nicht als "neu" wieder auftauchen
    conn.execute("BEGIN")
    conn.executemany(
        "INSERT OR IGNORE INTO dismissed_listings (listing_id, dismissed_at) VALUES (?, datetime('now'))",
        [(lid,) for lid in listing_ids],
    )
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM listings WHERE id IN ({placeholders})", ids)
    conn.execute("COMMIT")

    print(f"\n{bad} Anzeigen gelöscht und als dismissed eingetragen.")
    conn.close()


if __name__ == "__main__":
    main()
