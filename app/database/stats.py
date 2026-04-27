"""Crawl-/Benachrichtigungs-Logging und System-Statistiken."""

import os
from datetime import date, timedelta
from typing import Dict, List

from .core import DB_PATH, _current_db_path, _db


def log_crawl_run(platform: str, started_at: str, ended_at: str,
                  duration_s: float, found_count: int, term_count: int):
    with _db() as conn:
        conn.execute(
            "INSERT INTO crawl_log (platform, started_at, ended_at, duration_s, found_count, term_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (platform, started_at, ended_at, duration_s, found_count, term_count),
        )
        conn.commit()


def log_notification(notif_type: str, listing_count: int, recipient_count: int):
    with _db() as conn:
        conn.execute(
            "INSERT INTO notification_log (type, listing_count, recipient_count) VALUES (?, ?, ?)",
            (notif_type, listing_count, recipient_count),
        )
        conn.commit()


def get_price_stats() -> List[Dict]:
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


def get_system_stats() -> Dict:
    current_path = _current_db_path()
    try:
        db_size_bytes = os.path.getsize(str(current_path))
    except OSError:
        db_size_bytes = 0

    try:
        st = os.statvfs(str(current_path.parent))
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
        "db_size_bytes":       db_size_bytes,
        "db_size_mb":          round(db_size_bytes / (1024 * 1024), 2),
        "disk_free_bytes":     disk_free_bytes,
        "disk_free_gb":        round(disk_free_bytes / (1024 ** 3), 2),
        "disk_total_bytes":    disk_total_bytes,
        "disk_total_gb":       round(disk_total_bytes / (1024 ** 3), 2),
        "disk_used_pct":       round((1 - disk_free_bytes / disk_total_bytes) * 100, 1)
                               if disk_total_bytes else 0,
        "geocache_count":      geocache_count,
        "listings_total":      total,
        "listings_today":      today_count,
        "listings_last_7d":    last7_count,
        "listings_favorites":  favorites,
        "listings_free":       free_count,
        "listings_with_notes": with_notes,
        "listings_no_image":   no_image,
        "listings_duplicates": duplicates,
        "listings_dismissed":  dismissed,
        "platforms":           platforms,
        "top_terms":           top_terms,
        "daily_counts":        daily,
        "daily_max":           max((d["count"] for d in daily), default=0) or 1,
        "price_avg":           round(price_row["avg_p"], 2) if price_row and price_row["avg_p"] else None,
        "price_min":           round(price_row["min_p"], 2) if price_row and price_row["min_p"] else None,
        "price_max":           round(price_row["max_p"], 2) if price_row and price_row["max_p"] else None,
        "price_unknown_count": price_unknown,
        "crawl_stats":         crawl_stats,
        "total_crawl_runs":    total_crawls,
        "notif_stats":         notif_stats,
        "total_notifications": total_notifs,
        "search_term_count":   term_total,
        "active_term_count":   term_active,
        "profile_count":       profile_count,
        "migrations":          migrations,
    }
