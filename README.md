# 🍼 Baby-Crawler

Ein selbst gehosteter Web-Crawler für werdende Eltern – durchsucht **Kleinanzeigen.de**, **Shpock** und optional **Facebook Marketplace** automatisch nach Babysachen und benachrichtigt per E-Mail über neue Treffer.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?logo=flask)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- **Admin-UI** im Browser – Suchbegriffe per Klick hinzufügen, deaktivieren oder löschen
- **Mehrere Plattformen** gleichzeitig durchsuchen (Kleinanzeigen, Shpock, Facebook)
- **E-Mail-Benachrichtigungen** für neue Treffer (SMTP, z.B. Gmail)
- **Automatischer Scheduler** – kein manueller Cronjob nötig, Intervall frei einstellbar
- **Manueller Crawl** per Knopfdruck mit Live-Status-Anzeige
- **Filterbar** nach Suchbegriff oder Plattform
- **Preisfilter & Standort** pro Plattform konfigurierbar
- **Duplikat-Erkennung** – jede Anzeige wird nur einmal gemeldet
- **Docker-ready** – läuft auf jedem Linux-Server (Proxmox, Raspberry Pi, Cloud-VM)

---

## 🚀 Schnellstart

### Voraussetzungen

- Docker & Docker Compose
- Linux-Server (z.B. Proxmox VM/LXC, Raspberry Pi, jede Cloud-VM)

### Installation

```bash
git clone https://github.com/dein-name/baby-crawler.git
cd baby-crawler
docker compose up -d --build
```

Admin-UI aufrufen: **`http://<server-ip>:5000`**

### Proxmox: Docker schnell einrichten

```bash
apt update && apt install -y docker.io docker-compose-plugin
```

---

## 🖥️ Admin-UI

### Dashboard

Verwalte Suchbegriffe und sieh alle gefundenen Anzeigen in einer Kachelansicht.

- **Suchbegriff hinzufügen**: In das Eingabefeld tippen → "+ Add"
- **Aktivieren / Deaktivieren**: Toggle-Schalter neben dem Begriff
- **Löschen**: `×` erscheint beim Überfahren mit der Maus
- **Filtern**: `◎` zeigt nur Anzeigen für diesen Begriff
- **Manueller Crawl**: Schaltfläche "🚀 Jetzt crawlen" – Status aktualisiert sich live

### Einstellungen (`/settings`)

| Bereich | Konfigurierbar |
|---------|---------------|
| Kleinanzeigen.de | Aktiviert, Max. Preis, Standort, Radius |
| Shpock | Aktiviert, Max. Preis, Koordinaten, Radius |
| Facebook Marketplace | Aktiviert, Max. Preis, Standort |
| E-Mail | SMTP-Server, Absender, Empfänger, App-Passwort |
| Crawler | Intervall (Minuten), Max. Ergebnisse, Pause zwischen Anfragen |

---

## 📧 E-Mail-Benachrichtigungen

### Gmail einrichten

1. [App-Passwort erstellen](https://myaccount.google.com/apppasswords) (2FA muss aktiv sein)
2. In der Admin-UI unter **Einstellungen → E-Mail** eintragen:
   - SMTP-Server: `smtp.gmail.com` · Port: `587`
   - Absender: `deine-adresse@gmail.com`
   - App-Passwort: *(das erzeugte App-Passwort)*
   - Empfänger: *(Ziel-Adresse für Benachrichtigungen)*

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
├── run.py                  # Einstiegspunkt (Gunicorn)
├── data/                   # Persistentes Volume (SQLite-DB, FB-Session)
└── app/
    ├── __init__.py         # Flask App Factory
    ├── database.py         # SQLite-Datenbankschicht
    ├── routes.py           # Web-Routen & REST-API
    ├── crawler.py          # Crawl-Orchestrierung (Thread-safe)
    ├── scheduler.py        # APScheduler (Background)
    ├── notifier.py         # E-Mail-Versand (SMTP)
    ├── scrapers/
    │   ├── base.py         # Listing-Datenklasse
    │   ├── kleinanzeigen.py
    │   ├── shpock.py
    │   └── facebook.py
    └── templates/          # Jinja2 + Tailwind CSS (CDN, kein Build-Step)
```

### Tech-Stack

- **Backend**: Python 3.12, Flask 3, APScheduler 3
- **Datenbank**: SQLite (kein ORM, kein extra Container)
- **Scraping**: `requests` + `BeautifulSoup` / GraphQL-API / Playwright
- **Frontend**: Jinja2, Tailwind CSS via CDN, Vanilla JS
- **Deployment**: Docker + docker-compose, Gunicorn

---

## 🔧 Lokale Entwicklung

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
mkdir -p data
python run.py                 # → http://localhost:5000
```

> Hinweis: `database.py` nutzt den Pfad `/data/baby_crawler.db` (Docker-Volume). Für lokale Entwicklung in `database.py` auf `Path("./data/baby_crawler.db")` ändern.

---

## 🔄 Updates

```bash
git pull
docker compose up -d --build
```

## 📋 Logs

```bash
docker compose logs -f baby-crawler
```

## 💾 Backup

Die gesamte Datenbank ist eine einzelne Datei:

```bash
cp ./data/baby_crawler.db ./backup_$(date +%Y%m%d).db
```

Alte Anzeigen (älter als 30 Tage) werden automatisch bereinigt.

---

## 📄 Lizenz

MIT – frei verwendbar für private und kommerzielle Zwecke.

---

*Herzlichen Glückwunsch zur Schwangerschaft und viel Erfolg bei der Schnäppchenjagd! 🍼*
