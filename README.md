# 🍼 Baby-Crawler

Ein selbst gehosteter Web-Crawler für werdende Eltern – durchsucht **Kleinanzeigen.de**, **Shpock**, **Vinted**, **eBay** und optional **Facebook Marketplace** automatisch nach Babysachen und benachrichtigt per E-Mail über neue Treffer.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?logo=flask)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-218%20passed-brightgreen?logo=pytest)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Schnellstart (Docker)

```bash
git clone https://github.com/descipar/baby-crawler.git
cd baby-crawler
docker compose up -d --build
```

Admin-UI aufrufen: **`http://localhost:5000`**

---

## ✨ Features

### Suche & Filterung
- **5 Plattformen** gleichzeitig: Kleinanzeigen.de, Shpock, Vinted, eBay, Facebook Marketplace (optional)
- **Suchbegriffe** per Klick hinzufügen, aktivieren/deaktivieren, löschen (Anzeigen werden mitgelöscht)
- **Blacklist** – Stichworte wie „defekt" oder „bastler" automatisch ausfiltern
- **Entfernungsfilter** – Radius pro Plattform konfigurierbar; Radius 0 = kein Filter
- **Altersfilter** – nur Anzeigen der letzten 3h / 6h / 24h / 48h anzeigen
- **Plattform-Filter** – nur eine Plattform anzeigen
- **Suchbegriff-Filter** – Klick auf einen Suchbegriff filtert die Anzeigenliste
- **Exclude-Filter** – Begriffe live ausblenden (400 ms Debounce, ×-Button zum Zurücksetzen)
- **Duplikat-Erkennung** – jede Anzeige wird nur einmal gespeichert

### Anzeigen-Verwaltung
- **⭐ Favoriten** – Anzeigen markieren; Favoriten werden beim automatischen Aufräumen nie gelöscht
- **✕ Ausblenden** – einzelne Anzeigen dauerhaft verstecken; beim nächsten Crawl nicht wieder angezeigt
- **🎁 Gratis-Erkennung** – Anzeigen mit Preis 0 € / „zu verschenken" werden gesondert gekennzeichnet
- **📍 Entfernungsanzeige** – Luftlinie vom eigenen Standort zu jeder Anzeige (via OpenStreetMap)
- **Sortierung** – nach Datum, Preis (auf-/absteigend) oder Entfernung
- **Pagination** – 30 Anzeigen pro Seite, „Mehr laden"-Button

### Benachrichtigungen & Automatisierung
- **E-Mail-Alert** – Sofort-Benachrichtigung bei neuen Treffern (konfigurierbar)
- **Tages-Digest** – täglich zur konfigurierten Uhrzeit, unabhängig vom Sofort-Alert
- **Manueller Crawl** – per Knopfdruck mit Live-Log-Terminal und E-Mail bei neuen Treffern
- **Automatischer Scheduler** – konfigurierbares Intervall, kein Cronjob nötig
- **🔍 Verfügbarkeits-Check** – prüft periodisch ob Anzeigen noch online sind (HTTP 404/410 → automatisch löschen, inkl. Favoriten)

### Sonstiges
- **📊 Preisstatistik** – Durchschnitt, Min, Max und Gratis-Zähler pro Suchbegriff
- **📱 Mobil-optimiert** – responsive Layout, kollabierbare Sidebar, scrollbare Filter-Leiste
- **Docker-ready** – läuft auf jedem Linux-Server (Proxmox, Raspberry Pi, Cloud-VM)

---

## 🚀 Deployment

### Docker (empfohlen)

```bash
docker compose up -d --build   # Starten
docker compose logs -f          # Logs ansehen
docker compose down             # Stoppen
git pull && docker compose up -d --build  # Update
```

Bestehende Datenbanken werden automatisch migriert – keine Daten gehen verloren.

### Raspberry Pi 4

Stromsparend (~5 Watt), läuft still 24/7:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker pi
git clone https://github.com/descipar/baby-crawler.git /home/pi/baby-crawler
cd /home/pi/baby-crawler
docker compose up -d --build
```

### Lokal (ohne Docker)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py                   # http://localhost:5000
```

Die `.env`-Datei setzt `DATA_DIR=./data`. Optional: `SECRET_KEY=<langer-string>` für stabile Sessions.

---

## 🖥️ Admin-UI

### Dashboard

| Element | Funktion |
|---------|----------|
| Suchbegriff-Sidebar | Hinzufügen, aktivieren/deaktivieren, löschen (inkl. Anzeigen), als Filter-Klick |
| Filter-Leiste | Sortierung, Altersfilter, Plattform, Entfernung, Gratis, Favoriten, Exclude-Freitext |
| Anzeigen-Karte | Link zur Anzeige, ★ Favorit (AJAX), ✕ dauerhaft ausblenden (AJAX) |
| Status-Leiste | Crawl-Status, letzter/nächster Lauf, Gesamtzahl |
| 🚀 Jetzt crawlen | Startet manuellen Crawl mit Live-Log; E-Mail bei neuen Treffern |
| 📊 Preisstatistik | Aufklappbare Tabelle mit Avg/Min/Max pro Suchbegriff |

### Einstellungen (`/settings`)

| Bereich | Konfigurierbar |
|---------|---------------|
| Kleinanzeigen.de | Aktiviert, Max. Preis, Standort, Radius |
| Shpock | Aktiviert, Max. Preis, Standort, Radius (0 = kein Filter) |
| Vinted | Aktiviert, Max. Preis, Standort, Radius (0 = kein Filter) |
| eBay | Aktiviert, Max. Preis, Standort (PLZ oder Stadt), Radius |
| Facebook Marketplace | Aktiviert, Max. Preis, Standort |
| E-Mail | SMTP-Server/-Port, Absender, Empfänger (kommagetrennt), App-Passwort, Betreff |
| Tages-Digest | Aktiviert, Uhrzeit (z.B. `19:00`) |
| Crawler | Intervall (Min.), Max. Ergebnisse, Pause zw. Anfragen, Blacklist, Max. Alter |
| Verfügbarkeits-Check | Aktiviert, Intervall (Stunden), „Jetzt prüfen"-Button |
| Heimstandort | Stadt für Entfernungsberechnung |

---

## 📧 E-Mail einrichten

### Gmail

1. [App-Passwort erstellen](https://myaccount.google.com/apppasswords) (2FA muss aktiv sein)
2. In **Einstellungen → E-Mail** eintragen:
   - SMTP-Server: `smtp.gmail.com` · Port: `587`
   - Absender: `deine-adresse@gmail.com`
   - App-Passwort: *(das erzeugte App-Passwort)*
   - Empfänger: `kai@example.com, partner@example.com` (kommagetrennt)

### Weitere Anbieter

| Anbieter | SMTP-Server | Port |
|----------|-------------|------|
| GMX | mail.gmx.net | 587 |
| Web.de | smtp.web.de | 587 |
| Outlook | smtp.office365.com | 587 |

---

## 📘 Facebook Marketplace (optional)

Einmaliger interaktiver Login nötig:

```bash
docker exec -it baby-crawler python -c \
  "from app.scrapers.facebook import FacebookScraper; FacebookScraper({}).interactive_login()"
```

Danach Facebook in den Einstellungen aktivieren.

> ⚠️ Das automatische Auslesen von Facebook widerspricht den Nutzungsbedingungen. Nur für den privaten Gebrauch.

---

## 🏗️ Architektur

```
baby-crawler/
├── Dockerfile / docker-compose.yml
├── requirements.txt / pytest.ini
├── run.py                  # Einstiegspunkt
├── data/                   # SQLite-DB (persistentes Volume)
├── tests/                  # 218 Unit-Tests
│   ├── conftest.py
│   ├── test_crawler.py     # _is_free(), _is_blacklisted(), run_crawl()
│   ├── test_database.py    # CRUD, Migration, Dismiss, Sortierung
│   ├── test_geo.py         # Haversine, Geocoding-Cache
│   ├── test_notifier.py    # E-Mail-Builder, Badges
│   ├── test_routes.py      # Alle Flask-Routen und REST-API
│   ├── test_scrapers.py    # Vinted, Shpock, eBay
│   └── test_checker.py     # Verfügbarkeits-Check
└── app/
    ├── __init__.py         # Flask App Factory
    ├── database.py         # SQLite-Schicht (kein ORM, inkl. Migration)
    ├── routes.py           # Web-Routen & REST-API
    ├── crawler.py          # Crawl-Orchestrierung (Thread-safe)
    ├── checker.py          # Verfügbarkeits-Check (HEAD-Requests)
    ├── scheduler.py        # APScheduler: Crawl + Digest + Checker
    ├── notifier.py         # E-Mail (Sofort-Alert + Tages-Digest)
    ├── geo.py              # Nominatim-Geocoding + Haversine
    ├── scrapers/
    │   ├── base.py         # Listing-Datenklasse + Hilfsfunktionen
    │   ├── kleinanzeigen.py
    │   ├── shpock.py
    │   ├── vinted.py
    │   ├── ebay.py
    │   └── facebook.py
    └── templates/          # Jinja2 + Tailwind CSS (CDN, kein Build-Step)
```

**Tech-Stack**: Python 3.12 · Flask 3 · APScheduler 3 · SQLite (kein ORM) · Tailwind CSS via CDN · Docker + Gunicorn

---

## 🔧 Entwicklung & Tests

```bash
# Tests ausführen
python -m pytest tests/ -v

# Einzelne Testdatei
python -m pytest tests/test_database.py -v
```

Alle Tests laufen ohne externe Abhängigkeiten (HTTP und DB werden gemockt).

---

## 💾 Backup & Wartung

```bash
# Datenbank sichern
cp ./data/baby_crawler.db ./backup_$(date +%Y%m%d).db

# Logs ansehen
docker compose logs -f baby-crawler
```

Anzeigen älter als 30 Tage werden automatisch bereinigt. **Favoriten werden dabei nie gelöscht.**

---

## 📄 Lizenz

MIT – frei verwendbar für private und kommerzielle Zwecke.

---

*Viel Erfolg bei der Schnäppchenjagd! 🍼*
