"""APScheduler-Integration: Crawl-Intervall und Tages-Digest."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from . import database as db
from .crawler import run_crawl
from .notifier import send_digest

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler = None


def _run_digest():
    settings = db.get_settings()
    send_digest(settings)


def init_scheduler(app):
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Berlin")

    # Crawl-Job
    interval_minutes = int(db.get_setting("crawler_interval", "60"))
    _scheduler.add_job(
        run_crawl,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="crawl_job",
        name="Baby-Crawler Crawl",
        replace_existing=True,
    )

    # Tages-Digest-Job
    _schedule_digest()

    _scheduler.start()
    logger.info(f"Scheduler gestartet: Crawl alle {interval_minutes} Minuten.")
    return _scheduler


def _schedule_digest():
    """Richtet den täglichen Digest-Job basierend auf den Settings ein."""
    global _scheduler
    if _scheduler is None:
        return

    digest_enabled = db.get_setting("digest_enabled", "0") == "1"
    digest_time = db.get_setting("digest_time", "19:00")

    # Bestehenden Job entfernen falls vorhanden
    if _scheduler.get_job("digest_job"):
        _scheduler.remove_job("digest_job")

    if digest_enabled:
        try:
            hour, minute = (int(x) for x in digest_time.split(":"))
            _scheduler.add_job(
                _run_digest,
                trigger=CronTrigger(hour=hour, minute=minute),
                id="digest_job",
                name="Baby-Crawler Tages-Digest",
                replace_existing=True,
            )
            logger.info(f"Digest-Job eingerichtet für {digest_time} Uhr.")
        except (ValueError, AttributeError) as e:
            logger.error(f"Ungültige Digest-Zeit '{digest_time}': {e}")


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


def update_digest_schedule():
    """Neueinrichten des Digest-Jobs nach Einstellungsänderung."""
    _schedule_digest()


def get_next_run() -> str:
    global _scheduler
    if _scheduler is None:
        return "–"
    job = _scheduler.get_job("crawl_job")
    if job and job.next_run_time:
        return job.next_run_time.strftime("%d.%m.%Y %H:%M:%S")
    return "–"
