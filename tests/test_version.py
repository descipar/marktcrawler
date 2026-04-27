"""Tests für app/version.py und scripts/bake_version.py."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

from app.version import get_current_version, get_available_updates, _github_repo
from scripts.bake_version import _last_commit_from_log


class TestGetCurrentVersion:

    def test_liefert_alle_felder(self):
        v = get_current_version()
        assert "hash" in v
        assert "short_hash" in v
        assert "message" in v
        assert "date" in v

    def test_short_hash_ist_7_zeichen(self):
        v = get_current_version()
        if v["hash"] != "unbekannt":
            assert len(v["short_hash"]) == 7

    def test_env_var_hat_vorrang_vor_git(self, monkeypatch):
        monkeypatch.setenv("GIT_COMMIT", "abc1234567890")
        monkeypatch.setenv("GIT_DATE", "2026-01-01 00:00:00 +0000")
        monkeypatch.setenv("GIT_MESSAGE", "test commit")
        # _baked() muss leer sein damit env vars greifen
        with patch("app.version._baked", return_value={}):
            v = get_current_version()
        assert v["short_hash"] == "abc1234"
        assert v["date"] == "2026-01-01"
        assert v["message"] == "test commit"

    def test_baked_hat_vorrang_vor_env_var(self, monkeypatch):
        monkeypatch.setenv("GIT_COMMIT", "env0000000")
        with patch("app.version._baked", return_value={
            "hash": "baked123456", "date": "2026-02-01", "message": "baked msg"
        }):
            v = get_current_version()
        assert v["short_hash"] == "baked12"

    def test_fallback_wenn_nichts_verfuegbar(self, monkeypatch):
        monkeypatch.delenv("GIT_COMMIT", raising=False)
        monkeypatch.delenv("GIT_DATE", raising=False)
        monkeypatch.delenv("GIT_MESSAGE", raising=False)
        with patch("app.version._baked", return_value={}):
            with patch("app.version._git", return_value=""):
                v = get_current_version()
        assert v["hash"] == "unbekannt"
        assert v["short_hash"] == "unbekannt"


class TestGithubRepo:

    def test_env_var_wird_verwendet(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "owner/repo")
        assert _github_repo() == "owner/repo"

    def test_ssh_url_wird_geparst(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        with patch("app.version._git", return_value="git@github.com:owner/myrepo.git"):
            assert _github_repo() == "owner/myrepo"

    def test_https_url_wird_geparst(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        with patch("app.version._git", return_value="https://github.com/owner/myrepo.git"):
            assert _github_repo() == "owner/myrepo"

    def test_kein_remote_liefert_leerstring(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        with patch("app.version._git", return_value=""):
            assert _github_repo() == ""


class TestGetAvailableUpdates:

    def _mock_response(self, commits: list):
        resp = MagicMock()
        resp.json.return_value = {"commits": commits}
        resp.raise_for_status = MagicMock()
        return resp

    def _commit(self, sha, message, date="2026-04-27T10:00:00Z"):
        return {"sha": sha, "commit": {"message": message,
                "committer": {"date": date}}}

    def test_unbekannter_hash_liefert_none(self):
        assert get_available_updates("unbekannt") is None

    def test_leerer_hash_liefert_none(self):
        assert get_available_updates("") is None

    def test_kein_repo_liefert_none(self):
        with patch("app.version._github_repo", return_value=""):
            result = get_available_updates("abc1234")
        assert result is None

    def test_zwei_commits_neueste_zuerst(self):
        commits = [
            self._commit("aaa0001", "fix: erster", "2026-04-26T10:00:00Z"),
            self._commit("bbb0002", "feat: zweiter", "2026-04-27T10:00:00Z"),
        ]
        with patch("app.version._github_repo", return_value="o/r"), \
             patch("requests.get", return_value=self._mock_response(commits)):
            result = get_available_updates("xyz1234")
        assert result[0]["message"] == "feat: zweiter"
        assert result[1]["message"] == "fix: erster"
        assert result[0]["short_hash"] == "bbb0002"

    def test_api_fehler_liefert_none(self):
        with patch("app.version._github_repo", return_value="o/r"), \
             patch("requests.get", side_effect=Exception("timeout")):
            result = get_available_updates("abc1234")
        assert result is None


class TestLastCommitFromLog:

    def _line(self, msg, ts=1700000000):
        return f"abc123 def456 User <u@x.de> {ts} +0000\t{msg}"

    def test_normalen_commit_erkennt(self):
        lines = [self._line("commit: feat: etwas Neues")]
        _, msg, ts = _last_commit_from_log(lines)
        assert msg == "feat: etwas Neues"
        assert ts == 1700000000

    def test_fast_forward_wird_uebersprungen(self):
        lines = [
            self._line("commit: feat: letzter echter commit", ts=1700000001),
            self._line("pull: Fast-forward", ts=1700000002),
        ]
        _, msg, _ = _last_commit_from_log(lines)
        assert msg == "feat: letzter echter commit"

    def test_checkout_wird_uebersprungen(self):
        lines = [
            self._line("commit: fix: bugfix", ts=1700000001),
            self._line("checkout: moving from main to feature", ts=1700000002),
        ]
        _, msg, _ = _last_commit_from_log(lines)
        assert msg == "fix: bugfix"

    def test_commit_amend_wird_erkannt(self):
        lines = [self._line("commit (amend): fix: korrigiert")]
        _, msg, _ = _last_commit_from_log(lines)
        assert msg == "fix: korrigiert"

    def test_leeres_log_gibt_leer_zurueck(self):
        assert _last_commit_from_log([]) == ("", "", 0)

    def test_nur_noise_gibt_leer_zurueck(self):
        lines = [self._line("pull: Fast-forward"), self._line("checkout: moving")]
        assert _last_commit_from_log(lines) == ("", "", 0)
