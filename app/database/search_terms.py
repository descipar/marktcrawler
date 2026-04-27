"""Suchbegriff-CRUD."""

import sqlite3
from typing import Dict, List, Optional

from .core import _db


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
