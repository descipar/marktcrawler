"""Liest .git und schreibt app/_version.py – wird nur während docker build ausgeführt."""

import datetime
import pathlib
import sys

git = pathlib.Path(".git")
out = pathlib.Path("app/_version.py")


def _last_commit_from_log(log_lines: list) -> tuple:
    """Gibt (meta, message, timestamp) des letzten echten Commits zurück."""
    for line in reversed(log_lines):
        m, _, msg = line.partition("\t")
        if msg.startswith("commit"):
            parts = m.split()
            ts = int(parts[-2]) if len(parts) >= 2 else 0
            return m, msg.split(": ", 1)[-1].strip(), ts
    return "", "", 0

try:
    head = (git / "HEAD").read_text().strip()
    if head.startswith("ref:"):
        ref = head.split(" ", 1)[1].strip()
        commit = (git / ref).read_text().strip()
    else:
        commit = head

    # Branch-Log lesen; rückwärts iterieren um checkout/pull/fast-forward zu überspringen
    branch_log = git / "logs" / ref if head.startswith("ref:") else git / "logs" / "HEAD"
    log_lines = branch_log.read_text().strip().splitlines()
    meta, message, ts = _last_commit_from_log(log_lines)
    date = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
except Exception as e:
    print(f"bake_version: {e}", file=sys.stderr)
    commit = date = message = ""

out.write_text(
    f'COMMIT = {commit!r}\n'
    f'DATE   = {date!r}\n'
    f'MESSAGE = {message!r}\n'
)
print(f"bake_version: {commit[:7]} {date} – {message[:60]}")
