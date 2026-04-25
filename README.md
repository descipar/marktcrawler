# 🍼 Baby-Crawler

Ein selbst gehosteter Web-Crawler für werdende Eltern – durchsucht **Kleinanzeigen.de**, **Shpock**, **Vinted**, **eBay** und optional **Facebook Marketplace** automatisch nach Babysachen und benachrichtigt per E-Mail über neue Treffer.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?logo=flask)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-137%20passed-brightgreen?logo=pytest)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- **Admin-UI** im Browser – Suchbegriffe per Klick hinzufügen, deaktivieren oder löschen
- **Mehrere Plattformen** gleichzeitig durchsuchen (Kleinanzeigen, Shpock, Vinted, eBay, Facebook)
- **E-Mail-Benachrichtigungen** – Sofort-Alert bei neuen Treffern
- **Tages-Digest** – zusätzliche tägliche Zusammenfassung per E-Mail, zu konfigurierbarer Uhrzeit
- **Automatischer Scheduler** – kein manueller Cronjob nötig, Intervall frei einstellbar
- **Manueller Crawl** per Knopfdruck mit Live-Status-Anzeige
- **🎁 Gratis-Erkennung** – Anzeigen mit Preis 0 € / „zu verschenken" werden gesondert gekennzeichnet
- **⭐ Favoriten** – Anzeigen markieren; Favoriten werden beim automatischen Aufräumen nie gelöscht
- **📍 Entfernungsanzeige** – Luftlinie vom eigenen Standort zu jeder Anzeige (via OpenStreetMap)
- **📊 Preisstatistik** – Durchschnitt, Min und Max pro Suchbegriff
- **🚫 Blacklist** – Stichworte (z.B. „defekt", „bastler") automatisch ausfiltern
- **Altersfilter** – nur Anzeigen der letzten X Stunden anzeigen
- **Duplikat-Erkennung** – jede Anzeige wird nur einmal gemeldet
- **Docker-ready** – läuft auf jedem Linux-Server (Proxmox, Raspberry Pi, Cloud-VM)

---

## 🚀 Deployment-Optionen

### Option A – Raspberry Pi 4 (empfohlen)

Stromsparend (~5 Watt), läuft still 24/7, kein großer Server nötig.

```bash
# 1. Docker auf dem RPi installieren (einmalig)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker pi
# Terminal neu starten oder: newgrp docker

# 2. Repo klonen (einmalig)
git clone https://github.com/descipar/baby-crawler.git /home/pi/baby-crawler

# 3. Starten
cd /home/pi/baby-crawler
docker compose up -d --build
```

Admin-UI aufrufen: **`http://<rpi-ip>:5000`**

---

### Option B – Proxmox (VM oder LXC)

```bash
# Docker in Ubuntu/Debian LXC installieren (einmalig)
apt update && apt install -y docker.io docker-compose-plugin git

# Repo klonen (einmalig)
git clone https://github.com/descipar/baby-crawler.git /opt/baby-crawler

# Starten
cd /opt/baby-crawler
docker compose up -d --build
```

Admin-UI aufrufen: **`http://<proxmox-ip>:5000`**

---

### Option C – Lokal (zum Testen)

Kein Docker nötig – direkt mit Python starten, siehe [Lokale Entwicklung](#-lokale-entwicklung).

---

## 🖥️ Admin-UI

### Dashboard

Verwalte Suchbegriffe und sieh alle gefundenen Anzeigen in einer Kachelansicht.

- **Suchbegriff hinzufügen**: In das Eingabefeld tippen → "+ Add"
- **Aktivieren / Deaktivieren**: Toggle-Schalter neben dem Begriff
- **Löschen**: `×` erscheint beim Überfahren mit der Maus
- **Favorit markieren**: ★-Button auf jeder Anzeigekarte (AJAX, kein Seitenneulade)
- **Filter kombinieren**: Nur Favoriten · Nur Gratis · Letzte 3 h / 6 h / Heute / 48 h
- **Preisstatistik**: Aufklappbare Tabelle mit Avg/Min/Max pro Suchbegriff
- **Manueller Crawl**: Schaltfläche „🚀 Jetzt crawlen" – Status aktualisiert sich live

### Einstellungen (`/settings`)

| Bereich | Konfigurierbar |
|---------|---------------|
| Kleinanzeigen.de | Aktiviert, Max. Preis, Standort, Radius |
| Shpock | Aktiviert, Max. Preis, Standort, Radius |
| Vinted | Aktiviert, Max. Preis, Standort, Radius |
| eBay | Aktiviert, Max. Preis, Standort (PLZ oder Stadt), Radius |
| Facebook Marketplace | Aktiviert, Max. Preis, Standort |
| E-Mail | SMTP-Server, Absender, Empfänger (kommagetrennt), App-Passwort, Betreff (Alert + Digest) |
| Tages-Digest | Aktiviert, Uhrzeit (z.B. `19:00`) |
| Crawler | Intervall (Minuten), Max. Ergebnisse, Pause zw. Anfragen, Max. Alter (Stunden) |
| Blacklist | Ausgeschlossene Begriffe – einer pro Zeile |
| Heimstandort | Breitengrad + Längengrad für Entfernungsberechnung |

---

## 📧 E-Mail-Benachrichtigungen

### Gmail einrichten

1. [App-Passwort erstellen](https://myaccount.google.com/apppasswords) (2FA muss aktiv sein)
2. In der Admin-UI unter **Einstellungen → E-Mail** eintragen:
   - SMTP-Server: `smtp.gmail.com` · Port: `587`
   - Absender: `deine-adresse@gmail.com`
   - App-Passwort: *(das erzeugte App-Passwort)*
   - Empfänger: *(eine oder mehrere Adressen, kommagetrennt: `kai@example.com, partner@example.com`)*

### Tages-Digest

Zusätzlich zum Sofort-Alert kann täglich eine Zusammenfassung aller Anzeigen des Tages verschickt werden. Aktivierung und Uhrzeit unter **Einstellungen → Tages-Digest**.

### Andere Anbieter

| Anbieter | SMTP-Server | Port |
|----------|-------------|------|
| Gmail | smtp.gmail.com | 587 |
| GMX | mail.gmx.net | 587 |
| Web.de | smtp.web.de | 587 |
| Outlook | smtp.office365.com | 587 |

---

## 📘 Facebook Marketplace (optional)

Facebook erfordert einen einmaligen interaktiven Login:

```bash
docker exec -it baby-crawler python -c \
  "from app.scrapers.facebook import FacebookScraper; FacebookScraper({}).interactive_login()"
```

Danach Facebook in der Admin-UI unter Einstellungen aktivieren.

> ⚠️ **Hinweis:** Das automatische Auslesen von Facebook widerspricht den Nutzungsbedingungen. Dieses Feature ist ausschließlich für den privaten Gebrauch gedacht.

---

## 🏗️ Architektur

```
baby-crawler/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── run.py                  # Einstiegspunkt (Flask / Gunicorn)
├── data/                   # Persistentes Volume (SQLite-DB, FB-Session)
├── tests/                  # Unit-Tests (pytest, 115 Tests)
│   ├── conftest.py
│   ├── test_crawler.py
│   ├── test_database.py
│   ├── test_geo.py
│   ├── test_notifier.py
│   └── test_scrapers.py
└── app/
    ├── __init__.py         # Flask App Factory
    ├── database.py         # SQLite-Datenbankschicht (inkl. Migration)
    ├── routes.py           # Web-Routen & REST-API
    ├── crawler.py          # Crawl-Orchestrierung (Thread-safe)
    ├── scheduler.py        # APScheduler: Crawl-Intervall + Digest-Cron
    ├── notifier.py         # E-Mail-Versand (Sofort + Digest)
    ├── geo.py              # Geocoding (Nominatim/OSM) + Haversine
    ├── scrapers/
    │   ├── base.py         # Listing-Datenklasse + gemeinsame Hilfsfunktionen
    │   ├── kleinanzeigen.py
    │   ├── shpock.py
    │   ├── vinted.py
    │   ├── ebay.py
    │   └── facebook.py
    └── templates/          # Jinja2 + Tailwind CSS (CDN, kein Build-Step)
```

### Tech-Stack

- **Backend**: Python 3.12, Flask 3, APScheduler 3
- **Datenbank**: SQLite (kein ORM, kein extra Container), automatische Migration bei Updates
- **Scraping**: `requests` + `BeautifulSoup` / GraphQL-API / Playwright
- **Geocoding**: Nominatim (OpenStreetMap), Ergebnisse werden in der DB gecacht
- **Frontend**: Jinja2, Tailwind CSS via CDN, Vanilla JS
- **Deployment**: Docker + docker-compose, Gunicorn
- **Tests**: pytest, 137 Unit-Tests, keine externen Abhängigkeiten (Mocks für HTTP und DB)

---

## 🔧 Lokale Entwicklung

Kein Docker nötig – das Projekt läuft direkt mit Python.

```bash
# 1. Virtual Environment anlegen & Pakete installieren
cd baby-crawler
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Starten
python run.py
```

Admin-UI aufrufen: **`http://localhost:5000`**

Die `.env`-Datei im Projektroot setzt den Datenbankpfad automatisch auf `./data`. Für persistente Sessions empfiehlt es sich, zusätzlich einen stabilen `SECRET_KEY` zu setzen:

```
DATA_DIR=./data
SECRET_KEY=<langer-zufaelliger-string>
```

Im Docker-Container wird das Volume `/data` verwendet und `SECRET_KEY` als Umgebungsvariable in `docker-compose.yml` oder per `--env-file` übergeben.

### Tests ausführen

```bash
DATA_DIR=/tmp PYTHONPATH=. python -m pytest tests/ -v
```

---

## 🔄 Updates

```bash
git pull
docker compose up -d --build
```

Bestehende Datenbanken werden automatisch migriert – keine Daten gehen verloren.

## 📋 Logs

```bash
docker compose logs -f baby-crawler
```

## 💾 Backup

Die gesamte Datenbank ist eine einzelne Datei:

```bash
cp ./data/baby_crawler.db ./backup_$(date +%Y%m%d).db
```

Alte Anzeigen (älter als 30 Tage) werden automatisch bereinigt. **Favoriten werden dabei nie gelöscht.**

---

## 📄 Lizenz

MIT – frei verwendbar für private und kommerzielle Zwecke.

---

*Herzlichen Glückwunsch zur Schwangerschaft und viel Erfolg bei der Schnäppchenjagd! 🍼*
