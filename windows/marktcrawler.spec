# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Spec für den Windows-Build.
# SPECPATH ist der Ordner dieser Datei (= windows/).
# PROJ ist der Projekt-Root (eine Ebene darüber).

import os
from PyInstaller.utils.hooks import collect_data_files

PROJ = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(PROJ, "app", "templates"),  "app/templates"),
    (os.path.join(PROJ, "app", "_version.py"), "app"),
]

# langdetect bringt Sprach-Profile als Datendateien mit
datas += collect_data_files("langdetect")

# certifi-Zertifikate (für requests/HTTPS)
try:
    datas += collect_data_files("certifi")
except Exception:
    pass

hiddenimports = [
    # Flask-Kern
    "flask", "jinja2", "jinja2.ext", "werkzeug", "werkzeug.serving",
    "werkzeug.routing", "click",
    # APScheduler
    "apscheduler", "apscheduler.schedulers.background",
    "apscheduler.triggers.cron", "apscheduler.triggers.interval",
    "apscheduler.triggers.date", "apscheduler.jobstores.memory",
    "apscheduler.executors.pool",
    # HTTP / Scraping
    "requests", "urllib3", "charset_normalizer",
    "bs4", "lxml", "lxml.etree", "lxml._elementpath",
    # KI
    "anthropic", "openai", "httpx", "httpcore",
    # Tray
    "pystray", "pystray._base", "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    # Stdlib-Module die PyInstaller manchmal übersieht
    "sqlite3", "email.mime.multipart", "email.mime.text",
    "smtplib", "logging.handlers",
]

excludes = [
    "playwright", "pytest", "pytest_playwright",
    "gunicorn", "IPython", "notebook",
]

a = Analysis(
    [os.path.join(SPECPATH, "main_windows.py")],   # relativ zum Spec-Verzeichnis
    pathex=[PROJ],                                   # App-Package im Projekt-Root finden
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Marktcrawler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(SPECPATH, "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Marktcrawler",
)
