#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# ── .env anlegen falls nicht vorhanden ──────────────────────
if [ ! -f ".env" ]; then
    printf "DATA_DIR=./data\nSECRET_KEY=%s\n" \
        "$(python -c 'import secrets; print(secrets.token_hex(32))')" > .env
    echo "[INFO] .env erstellt."
fi

# ── Virtual Environment anlegen falls nicht vorhanden ────────
if [ ! -f ".venv/Scripts/activate" ] && [ ! -f ".venv/bin/activate" ]; then
    echo "[INFO] Erstelle Virtual Environment..."
    python -m venv .venv
fi

# Windows (Git Bash) vs. Unix
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# ── Abhängigkeiten installieren ───────────────────────────────
echo "[INFO] Prüfe Abhängigkeiten..."
pip install -q -r requirements.txt

# ── Datenverzeichnis anlegen ──────────────────────────────────
mkdir -p data

# ── Starten ───────────────────────────────────────────────────
echo ""
echo " Baby-Crawler läuft auf http://localhost:5000"
echo " Strg+C zum Beenden."
echo ""
python run.py
