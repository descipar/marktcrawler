"""Tests für app/scheduler.py: start_date-Logik nach Server-Neustart."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from app.scheduler import _calc_start_date, _schedule_digest


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TestCalcStartDate:

    def test_keine_last_end_gibt_none(self):
        assert _calc_start_date("", 15, 60) is None
        assert _calc_start_date(None, 15, 60) is None

    def test_ueberfaelliger_job_startet_mit_versatz(self):
        last_end = (_utcnow() - timedelta(minutes=30)).isoformat()
        result = _calc_start_date(last_end, 15, 60)
        assert result is not None
        delta = (result - _utcnow()).total_seconds()
        assert 55 <= delta <= 65  # ca. 60 Sekunden Versatz

    def test_versatz_wird_korrekt_angewendet(self):
        last_end = (_utcnow() - timedelta(hours=2)).isoformat()
        result_0 = _calc_start_date(last_end, 15, stagger_seconds=60)
        result_1 = _calc_start_date(last_end, 15, stagger_seconds=75)
        assert result_1 > result_0
        diff = (result_1 - result_0).total_seconds()
        assert 14 <= diff <= 16  # 15 Sekunden Unterschied

    def test_nicht_ueberfaelliger_job_behaelt_faelligkeitszeitpunkt(self):
        last_end = (_utcnow() - timedelta(minutes=10)).isoformat()
        result = _calc_start_date(last_end, 30, 60)  # nächster Lauf in 20 Min.
        assert result is not None
        delta = (result - _utcnow()).total_seconds()
        assert 18 * 60 <= delta <= 21 * 60  # ~20 Minuten in der Zukunft

    def test_genau_jetzt_faellig_gilt_als_ueberfaellig(self):
        last_end = (_utcnow() - timedelta(minutes=15, seconds=1)).isoformat()
        result = _calc_start_date(last_end, 15, 60)
        assert result is not None
        delta = (result - _utcnow()).total_seconds()
        assert delta < 120  # wird zeitnah gestartet

    def test_ungueltige_last_end_gibt_none(self):
        assert _calc_start_date("kein-datum", 15, 60) is None
        assert _calc_start_date("2024-99-99", 15, 60) is None


class TestScheduleDigest:

    def _make_scheduler(self):
        mock = MagicMock()
        mock.get_job.return_value = None
        return mock

    def test_digest_deaktiviert_kein_job(self):
        mock_scheduler = self._make_scheduler()
        with patch("app.scheduler._scheduler", mock_scheduler), \
             patch("app.scheduler.db.get_setting", side_effect=lambda k, d="": "0" if k == "digest_enabled" else d):
            _schedule_digest()
        mock_scheduler.add_job.assert_not_called()

    def test_gueltiger_digest_time_richtet_job_ein(self):
        mock_scheduler = self._make_scheduler()
        settings = {"digest_enabled": "1", "digest_time": "19:00"}
        with patch("app.scheduler._scheduler", mock_scheduler), \
             patch("app.scheduler.db.get_setting", side_effect=lambda k, d="": settings.get(k, d)):
            _schedule_digest()
        mock_scheduler.add_job.assert_called_once()
        kwargs = mock_scheduler.add_job.call_args[1]
        assert kwargs["id"] == "digest_job"

    def test_ungueltiger_digest_time_kein_job(self):
        mock_scheduler = self._make_scheduler()
        settings = {"digest_enabled": "1", "digest_time": "ungueltig"}
        with patch("app.scheduler._scheduler", mock_scheduler), \
             patch("app.scheduler.db.get_setting", side_effect=lambda k, d="": settings.get(k, d)):
            _schedule_digest()
        mock_scheduler.add_job.assert_not_called()

    def test_remove_job_wenn_bereits_vorhanden(self):
        mock_scheduler = self._make_scheduler()
        mock_scheduler.get_job.return_value = MagicMock()
        settings = {"digest_enabled": "1", "digest_time": "08:30"}
        with patch("app.scheduler._scheduler", mock_scheduler), \
             patch("app.scheduler.db.get_setting", side_effect=lambda k, d="": settings.get(k, d)):
            _schedule_digest()
        mock_scheduler.remove_job.assert_called_once_with("digest_job")
