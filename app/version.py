"""Ermittelt die aktuelle App-Version und verfügbare Updates via GitHub API."""

import os
import re
import subprocess
from typing import Optional


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


def _baked() -> dict:
    """Liest die beim Docker-Build eingebrannte _version.py, falls vorhanden."""
    try:
        from app import _version  # type: ignore
        return {
            "hash": _version.COMMIT,
            "date": _version.DATE,
            "message": _version.MESSAGE,
        }
    except ImportError:
        return {}


def get_current_version() -> dict:
    baked = _baked()
    commit = baked.get("hash") or os.environ.get("GIT_COMMIT") or _git("rev-parse", "HEAD")
    date = baked.get("date") or os.environ.get("GIT_DATE") or _git("log", "-1", "--format=%ci")
    message = baked.get("message") or os.environ.get("GIT_MESSAGE") or _git("log", "-1", "--format=%s")
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
        return commits
    except Exception:
        return None
