"""Ermittelt die aktuelle App-Version und verfügbare Updates via GitHub API."""

import os
import re
import subprocess
import threading
import time
from typing import Optional

_cache_lock = threading.Lock()
_updates_cache: dict = {}
_CACHE_TTL = 3600


def _git(*args) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        ).strip()
    except Exception:
        return ""


def get_current_version() -> dict:
    commit = os.environ.get("GIT_COMMIT") or _git("rev-parse", "HEAD")
    date = os.environ.get("GIT_DATE") or _git("log", "-1", "--format=%ci")
    message = os.environ.get("GIT_MESSAGE") or _git("log", "-1", "--format=%s")
    return {
        "hash": commit or "unbekannt",
        "short_hash": commit[:7] if commit else "unbekannt",
        "message": message or "–",
        "date": date[:10] if date else "–",
    }


def _github_repo() -> str:
    repo = os.environ.get("GITHUB_REPO", "")
    if repo:
        return repo
    remote = _git("remote", "get-url", "origin")
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote)
    return m.group(1) if m else ""


def get_available_updates(current_hash: str) -> Optional[list]:
    """Liefert neuere Commits aus GitHub. None bei Fehler oder unbekanntem Hash."""
    if not current_hash or current_hash == "unbekannt":
        return None

    with _cache_lock:
        entry = _updates_cache.get(current_hash)
        if entry and time.time() - entry["ts"] < _CACHE_TTL:
            return entry["data"]

    repo = _github_repo()
    if not repo:
        return None

    url = f"https://api.github.com/repos/{repo}/compare/{current_hash}...main"
    try:
        import requests as _req
        resp = _req.get(url, headers={"User-Agent": "marktcrawler/1.0"}, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        commits = [
            {
                "short_hash": c["sha"][:7],
                "message": c["commit"]["message"].split("\n")[0],
                "date": c["commit"]["committer"]["date"][:10],
            }
            for c in data.get("commits", [])
        ]
        commits.reverse()
        with _cache_lock:
            _updates_cache[current_hash] = {"ts": time.time(), "data": commits}
        return commits
    except Exception:
        return None
