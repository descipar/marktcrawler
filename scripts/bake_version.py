"""Liest .git und schreibt app/_version.py – wird nur während docker build ausgeführt."""

import datetime
import pathlib
import sys

git = pathlib.Path(".git")
out = pathlib.Path("app/_version.py")

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
    meta = message = ""
    for line in reversed(log_lines):
        m, _, msg = line.partition("\t")
        if msg.startswith("commit"):
            meta, message = m, msg.split(": ", 1)[-1].strip()
            break
    parts = meta.split()
    ts = int(parts[-2]) if len(parts) >= 2 else 0
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
