"""Liest .git und schreibt app/_version.py – wird nur während docker build ausgeführt."""

import datetime
import pathlib
import sys
import zlib

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


def _commit_from_object(git_path: pathlib.Path, sha: str) -> tuple:
    """Liest Datum und Betreff direkt aus dem Git-Commit-Objekt (loose objects).

    Zuverlässiger als der Reflog, da er das exakte committer-Datum liefert –
    unabhängig davon ob der letzte Reflog-Eintrag ein commit oder pull war.
    """
    if not sha or len(sha) < 4:
        return 0, ""
    obj_file = git_path / "objects" / sha[:2] / sha[2:]
    if not obj_file.exists():
        return 0, ""
    try:
        content = zlib.decompress(obj_file.read_bytes()).partition(b"\0")[2].decode("utf-8", errors="replace")
        ts, subject, in_body = 0, "", False
        for line in content.split("\n"):
            if in_body:
                if line.strip():
                    subject = line.strip()
                    break
            elif not line:
                in_body = True
            elif line.startswith("committer "):
                parts = line.split()
                try:
                    utc_ts = int(parts[-2])
                    tz = parts[-1]  # e.g. "+0200"
                    sign = 1 if tz[0] == "+" else -1
                    tz_secs = sign * (int(tz[1:3]) * 3600 + int(tz[3:5]) * 60)
                    ts = utc_ts + tz_secs  # lokaler Timestamp für korrektes Datum
                except (ValueError, IndexError):
                    pass
        return ts, subject
    except Exception:
        return 0, ""


try:
    head = (git / "HEAD").read_text().strip()
    if head.startswith("ref:"):
        ref = head.split(" ", 1)[1].strip()
        commit = (git / ref).read_text().strip()
    else:
        commit = head
        ref = "HEAD"

    # Primär: Commit-Objekt lesen → exaktes Datum + echte Commit-Message
    ts, message = _commit_from_object(git, commit)

    if not ts:
        # Fallback: Branch-Log (funktioniert bei direkten Commits ohne git gc)
        branch_log = git / "logs" / ref if ref != "HEAD" else git / "logs" / "HEAD"
        log_lines = branch_log.read_text().strip().splitlines()
        _, message_from_log, ts = _last_commit_from_log(log_lines)
        message = message or message_from_log

        if not ts:
            # Letzter Fallback: Timestamp aus neuestem Reflog-Eintrag
            for line in reversed(log_lines):
                m, _, _ = line.partition("\t")
                parts = m.split()
                try:
                    candidate = int(parts[-2])
                    if candidate > 0:
                        ts = candidate
                        break
                except (ValueError, IndexError):
                    pass

    date = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d") if ts else ""
except Exception as e:
    print(f"bake_version: {e}", file=sys.stderr)
    commit = date = message = ""

out.write_text(
    f'COMMIT = {commit!r}\n'
    f'DATE   = {date!r}\n'
    f'MESSAGE = {message!r}\n'
)
print(f"bake_version: {commit[:7]} {date} – {message[:60]}")
