"""APScheduler-Integration: ein Job pro Plattform + Tages-Digest + Verfügbarkeits-Check."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from . import database as db
from .checker import run_availability_check
from .crawler import run_crawl, DEFAULT_INTERVALS, PLATFORM_SCRAPER_MAP
from .notifier import send_digest

logger = logging.getLogger(__name__)

PLATFORMS = list(PLATFORM_SCRAPER_MAP.keys())

_scheduler: BackgroundScheduler = None


def _run_digest():
    settings = db.get_settings()
    send_digest(settings)


def init_scheduler(app):
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Berlin")

    _schedule_platform_jobs()
    _schedule_digest()
    _schedule_availability_check()

    _scheduler.start()
    logger.info("Scheduler gestartet.")
    return _scheduler


def _schedule_platform_jobs():
    """Richtet einen APScheduler-Job pro aktivierter Plattform ein."""
    global _scheduler
    if _scheduler is None:
        return

    global_default = _safe_int(db.get_setting("crawler_interval", "30"), 30)

    for platform in PLATFORMS:
        job_id = f"crawl_{platform}"
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)

        if db.get_setting(f"{platform}_enabled", "0") != "1":
            continue

        platform_default = DEFAULT_INTERVALS.get(platform, global_default)
        minutes = _safe_int(
            db.get_setting(f"{platform}_interval", str(platform_default)),
            platform_default,
        )
        minutes = max(1, minutes)

        _scheduler.add_job(
            run_crawl,
            trigger=IntervalTrigger(minutes=minutes),
            kwargs={"platform": platform},
            id=job_id,
            name=f"Baby-Crawler [{platform}]",
            replace_existing=True,
        )
        logger.info(f"[{platform}] Crawl-Job: alle {minutes} Minuten.")


def _schedule_digest():
    global _scheduler
    if _scheduler is None:
        return

    if _scheduler.get_job("digest_job"):
        _scheduler.remove_job("digest_job")

    if db.get_setting("digest_enabled", "0") != "1":
        return

    digest_time = db.get_setting("digest_time", "19:00")
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


def _schedule_availability_check():
    global _scheduler
    if _scheduler is None:
        return

    if _scheduler.get_job("availability_job"):
        _scheduler.remove_job("availability_job")

    if db.get_setting("availability_check_enabled", "1") != "1":
        return

    hours = max(1, _safe_int(db.get_setting("availability_check_interval_hours", "3"), 3))
    _scheduler.add_job(
        run_availability_check,
        trigger=IntervalTrigger(hours=hours),
        id="availability_job",
        name="Baby-Crawler Verfügbarkeits-Check",
        replace_existing=True,
    )
    logger.info(f"Verfügbarkeits-Check: alle {hours} Stunden.")


def update_platform_schedules():
    """Alle Plattform-Jobs nach Einstellungsänderung neu einrichten."""
    _schedule_platform_jobs()


def update_digest_schedule():
    _schedule_digest()


def update_availability_schedule():
    _schedule_availability_check()


def get_next_run() -> str:
    """Früheste nächste Ausführung über alle Plattform-Jobs."""
    global _scheduler
    if _scheduler is None:
        return "–"
    next_times = [
        job.next_run_time
        for platform in PLATFORMS
        if (job := _scheduler.get_job(f"crawl_{platform}")) and job.next_run_time
    ]
    return min(next_times).strftime("%d.%m.%Y %H:%M:%S") if next_times else "–"


def get_next_runs() -> dict:
    """Nächste Ausführung pro Plattform."""
    global _scheduler
    if _scheduler is None:
        return {}
    result = {}
    for platform in PLATFORMS:
        job = _scheduler.get_job(f"crawl_{platform}")
        if job and job.next_run_time:
            result[platform] = job.next_run_time.strftime("%d.%m.%Y %H:%M:%S")
    return result


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
