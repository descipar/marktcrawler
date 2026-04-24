"""APScheduler-Integration: Crawl-Intervall aus der Datenbank."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from . import database as db
from .crawler import run_crawl

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler = None


def init_scheduler(app):
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Berlin")

    interval_minutes = int(db.get_setting("crawler_interval", "60"))
    _scheduler.add_job(
        run_crawl,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="crawl_job",
        name="Baby-Crawler",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"Scheduler gestartet: alle {interval_minutes} Minuten.")

    return _scheduler


def update_interval(minutes: int):
    """Aktualisiert das Crawl-Intervall zur Laufzeit."""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.reschedule_job(
        "crawl_job",
        trigger=IntervalTrigger(minutes=minutes),
    )
    logger.info(f"Crawl-Intervall auf {minutes} Minuten geändert.")


def get_next_run() -> str:
    """Gibt den nächsten geplanten Lauf als lesbaren String zurück."""
    global _scheduler
    if _scheduler is None:
        return "–"
    job = _scheduler.get_job("crawl_job")
    if job and job.next_run_time:
        return job.next_run_time.strftime("%d.%m.%Y %H:%M:%S")
    return "–"
