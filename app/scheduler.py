"""APScheduler-Integration: ein Job pro Plattform + Tages-Digest + Verfügbarkeits-Check."""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from . import database as db
from .checker import run_availability_check
from .crawler import run_crawl, DEFAULT_INTERVALS, PLATFORM_SCRAPER_MAP
from .notifier import send_digest, notify_pending

logger = logging.getLogger(__name__)

PLATFORMS = list(PLATFORM_SCRAPER_MAP.keys())

_scheduler: BackgroundScheduler = None


def _run_digest():
    settings = db.get_settings()
    send_digest(settings)


def _run_digest_for_profile(profile_id: int):
    settings = db.get_settings()
    profile = db.get_profile(profile_id)
    if profile and profile.get("email"):
        send_digest(settings, recipient=profile["email"])


def _run_notify_pending():
    settings = db.get_settings()
    notify_pending(settings)


def init_scheduler(app):
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Berlin")

    _schedule_platform_jobs()
    _schedule_notify_job()
    _schedule_digest()
    _schedule_profile_digests()
    _schedule_availability_check()

    _scheduler.start()
    logger.info("Scheduler gestartet.")
    return _scheduler


def _calc_start_date(last_end_str: str, minutes: int, stagger_seconds: int) -> datetime | None:
    """Berechnet start_date für IntervalTrigger nach Server-Neustart.

    Ist der nächste fällige Lauf bereits überfällig, wird er nach
    stagger_seconds gestartet statt erst nach dem vollen Intervall zu warten.
    Ist er noch nicht fällig, wird der exakte Fälligkeitszeitpunkt gesetzt.
    Fehlt last_end, wird None zurückgegeben (APScheduler-Standard).

    Wichtig: Rückgabe ist timezone-aware (UTC), damit APScheduler mit
    timezone="Europe/Berlin" die Konvertierung korrekt vornimmt.
    Naive Datetimes würden als Berliner Lokalzeit interpretiert (±2h Versatz).
    """
    if not last_end_str:
        return None
    try:
        last_end = datetime.fromisoformat(last_end_str).replace(tzinfo=timezone.utc)
        next_due = last_end + timedelta(minutes=minutes)
        now = datetime.now(timezone.utc)
        if next_due <= now:
            return now + timedelta(seconds=stagger_seconds)
        return next_due
    except ValueError:
        return None


def _schedule_platform_jobs():
    """Richtet einen APScheduler-Job pro aktivierter Plattform ein."""
    global _scheduler
    if _scheduler is None:
        return

    global_default = _safe_int(db.get_setting("crawler_interval", "30"), 30)
    stagger_idx = 0  # Versatz-Zähler für überfällige Starts

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

        # 60s Basisverzögerung + 15s pro Plattform → kein gleichzeitiger Start
        start_date = _calc_start_date(
            db.get_setting(f"{platform}_last_crawl_end", ""),
            minutes,
            stagger_seconds=60 + stagger_idx * 15,
        )
        stagger_idx += 1

        _scheduler.add_job(
            run_crawl,
            trigger=IntervalTrigger(minutes=minutes, start_date=start_date),
            kwargs={"platform": platform},
            id=job_id,
            name=f"Marktcrawler [{platform}]",
            replace_existing=True,
        )
        next_info = f", nächster Start: {start_date.strftime('%H:%M:%S')}" if start_date else ""
        logger.info(f"[{platform}] Crawl-Job: alle {minutes} Minuten{next_info}.")


def _schedule_notify_job():
    global _scheduler
    if _scheduler is None:
        return

    if _scheduler.get_job("notify_job"):
        _scheduler.remove_job("notify_job")

    _scheduler.add_job(
        _run_notify_pending,
        trigger=IntervalTrigger(minutes=15),
        id="notify_job",
        name="Marktcrawler Benachrichtigung",
        replace_existing=True,
    )
    logger.info("Benachrichtigungs-Job: alle 15 Minuten.")


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
            name="Marktcrawler Tages-Digest",
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

    # start_date berechnen: verhindert, dass nach Server-Neustart der volle
    # Intervall neu abgewartet wird. Wenn der letzte Lauf bekannt ist und der
    # nächste fällige Termin in der Vergangenheit liegt, 1 Min. Vorlauf setzen.
    start_date = None
    last_run_str = db.get_setting("availability_last_run", "")
    if last_run_str:
        try:
            last_run = datetime.fromisoformat(last_run_str).replace(tzinfo=timezone.utc)
            next_due = last_run + timedelta(hours=hours)
            now = datetime.now(timezone.utc)
            start_date = now + timedelta(minutes=1) if next_due <= now else next_due
        except ValueError:
            pass

    _scheduler.add_job(
        run_availability_check,
        trigger=IntervalTrigger(hours=hours, start_date=start_date),
        id="availability_job",
        name="Marktcrawler Verfügbarkeits-Check",
        replace_existing=True,
    )
    logger.info(f"Verfügbarkeits-Check: alle {hours} Stunden (nächster Lauf: {start_date or 'sofort +interval'}).")


def update_platform_schedules():
    """Alle Plattform-Jobs nach Einstellungsänderung neu einrichten."""
    _schedule_platform_jobs()


def _schedule_profile_digests():
    global _scheduler
    if _scheduler is None:
        return

    for job in _scheduler.get_jobs():
        if job.id.startswith("digest_profile_"):
            _scheduler.remove_job(job.id)

    for profile in db.get_profiles():
        if not profile.get("email") or profile.get("notify_mode") not in ("digest_only", "both"):
            continue
        digest_time = profile.get("digest_time") or "19:00"
        try:
            hour, minute = (int(x) for x in digest_time.split(":"))
            _scheduler.add_job(
                _run_digest_for_profile,
                trigger=CronTrigger(hour=hour, minute=minute),
                args=[profile["id"]],
                id=f"digest_profile_{profile['id']}",
                name=f"Digest [{profile['name']}]",
                replace_existing=True,
            )
            logger.info(f"Digest-Job für Profil '{profile['name']}' um {digest_time} Uhr.")
        except Exception as e:
            logger.error(f"Digest-Job Profil {profile['id']}: {e}")


def update_digest_schedule():
    _schedule_digest()


def update_profile_digest_schedules():
    _schedule_profile_digests()


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
    return min(next_times).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if next_times else "–"


def get_next_runs() -> dict:
    """Nächste Ausführung pro Plattform."""
    global _scheduler
    if _scheduler is None:
        return {}
    result = {}
    for platform in PLATFORMS:
        job = _scheduler.get_job(f"crawl_{platform}")
        if job and job.next_run_time:
            result[platform] = job.next_run_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return result


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
