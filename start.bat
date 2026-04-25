@echo off
setlocal
cd /d "%~dp0"

:: ── .env anlegen falls nicht vorhanden ──────────────────────
if not exist ".env" (
    echo DATA_DIR=./data> .env
    echo SECRET_KEY=%RANDOM%%RANDOM%%RANDOM%>> .env
    echo [INFO] .env erstellt.
)

:: ── Virtual Environment anlegen falls nicht vorhanden ───────
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Erstelle Virtual Environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [FEHLER] python nicht gefunden. Bitte Python 3.12 installieren.
        pause
        exit /b 1
    )
)

:: ── Abhängigkeiten installieren ──────────────────────────────
echo [INFO] Prüfe Abhängigkeiten...
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

:: ── Datenverzeichnis anlegen ─────────────────────────────────
if not exist "data" mkdir data

:: ── Starten ──────────────────────────────────────────────────
echo.
echo  Baby-Crawler laeuft auf http://localhost:5000
echo  Strg+C zum Beenden.
echo.
python run.py

pause
