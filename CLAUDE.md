# CLAUDE.md – Baby-Crawler

Dieses Dokument beschreibt die Architektur und Konventionen des Projekts für KI-Assistenten.

## Projektübersicht

Web-App zum automatisierten Durchsuchen von Kleinanzeigen-Plattformen (Kleinanzeigen.de, Shpock, Facebook Marketplace) nach Babysachen. Neue Treffer werden per E-Mail gemeldet. Verwaltung über eine Flask-basierte Admin-UI.

## Tech-Stack

- **Backend**: Python 3.12, Flask 3, APScheduler 3
- **Datenbank**: SQLite (via `sqlite3` Standardbibliothek, kein ORM)
- **Scraping**: `requests` + `BeautifulSoup`/`lxml` (Kleinanzeigen), GraphQL-API (Shpock), Playwright (Facebook)
- **Frontend**: Jinja2-Templates, Tailwind CSS (CDN), Vanilla JS (kein Build-Step)
- **Deployment**: Docker + docker-compose

## Verzeichnisstruktur

```
baby-crawler-v2/
├── run.py                      # Gunicorn-Einstiegspunkt → create_app()
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── data/                       # Persistentes Volume (SQLite-DB, FB-Session)
└── app/
    ├── __init__.py             # Flask App Factory, initialisiert DB + Scheduler
    ├── database.py             # Gesamte SQLite-Schicht (kein ORM)
    ├── routes.py               # Alle Flask-Routen + REST-API (Blueprint "main")
    ├── crawler.py              # Crawl-Orchestrierung, threading.Lock, run_crawl_async()
    ├── scheduler.py            # APScheduler BackgroundScheduler
    ├── notifier.py             # SMTP E-Mail-Versand
    ├── scrapers/
    │   ├── base.py             # Listing-Dataclass (gemeinsame Datenstruktur)
    │   ├── kleinanzeigen.py    # requests + BeautifulSoup
    │   ├── shpock.py           # GraphQL-API POST
    │   └── facebook.py        # Playwright headless (optional)
    └── templates/
        ├── base.html           # Navbar, Flash-Messages, Tailwind-Setup
        ├── index.html          # Dashboard: Suchbegriffe + Anzeigen-Grid + Live-Status
        ├── _listing_card.html  # Wiederverwendbares Anzeigen-Kachel-Partial
        └── settings.html      # Einstellungsformular (alle Plattformen + E-Mail)
```

## Datenbankschema

Drei Tabellen in `/data/baby_crawler.db`:

```sql
search_terms (id, term TEXT UNIQUE, enabled INT, created_at)
settings     (key TEXT PRIMARY KEY, value TEXT)
listings     (id, listing_id TEXT UNIQUE, platform, title, price,
              location, url, image_url, description, search_term, found_at)
```

Alle Settings (Plattform-Konfiguration, E-Mail, Crawler-Intervall) werden als Key-Value-Paare in `settings` gespeichert. Default-Werte stehen in `database.DEFAULT_SETTINGS`.

## Wichtige Konventionen

- **Scraper-Interface**: Jeder Scraper hat `__init__(self, settings: dict)` und `search(self, term: str, max_results: int) -> List[Listing]`. `settings` ist das komplette Dict aus `db.get_settings()`.
- **Neue Scraper hinzufügen**: Neue Klasse in `app/scrapers/`, in `scrapers/__init__.py` exportieren, in `crawler.py` in der Scraper-Liste eintragen, in `routes.py` und `settings.html` entsprechende Felder ergänzen.
- **Kein ORM**: Alle DB-Zugriffe direkt mit `sqlite3` in `database.py`. Neue Abfragen dort als Funktion anlegen.
- **Kein JS-Build**: Tailwind via CDN. Kein npm, kein Webpack. JS direkt in den Templates als `<script>`-Blöcke.
- **Thread-Safety**: `crawler.py` nutzt `threading.Lock` + globales `_running`-Flag. Nie direkt aus anderen Modulen `run_crawl()` ohne `run_crawl_async()` aufrufen.
- **Settings-Checkboxen**: In HTML-Forms senden Checkboxen keinen Wert wenn nicht angehakt. `routes.py → save_settings()` behandelt das explizit mit `"1" if request.form.get(key) else "0"`.

## Lokale Entwicklung

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Datenbank-Pfad für lokale Entwicklung überschreiben
export DB_PATH=./dev_data/baby_crawler.db
mkdir -p dev_data

python run.py                     # startet auf http://localhost:5000
```

Hinweis: `app/database.py` nutzt hardcodierten Pfad `/data/baby_crawler.db` (Docker-Volume). Für lokale Entwicklung `DB_PATH` in `database.py` auf `Path("./data/baby_crawler.db")` ändern oder eine Umgebungsvariable einbauen.

## Docker

```bash
docker compose up -d --build      # Starten
docker compose logs -f            # Logs
docker compose down               # Stoppen
```

Die SQLite-DB liegt im Volume `./data/` und überlebt Container-Neustarts.

## API-Endpunkte

| Method | URL | Beschreibung |
|--------|-----|-------------|
| GET | `/` | Dashboard |
| POST | `/terms` | Suchbegriff hinzufügen (`form: term`) |
| POST | `/terms/<id>/delete` | Suchbegriff löschen |
| POST | `/terms/<id>/toggle` | Aktivieren / Deaktivieren |
| GET | `/settings` | Einstellungsseite |
| POST | `/settings` | Einstellungen speichern |
| POST | `/api/crawl` | Crawl manuell starten (JSON-Response) |
| GET | `/api/status` | Crawler-Status als JSON |
| GET | `/api/listings` | Anzeigen als JSON (`?term=`, `?platform=`, `?limit=`) |

## Bekannte Einschränkungen

- Kleinanzeigen.de ändert gelegentlich seine HTML-Selektoren → CSS-Selektoren in `kleinanzeigen.py._parse()` ggf. anpassen.
- Facebook Marketplace benötigt interaktiven einmaligen Login und Playwright (`playwright install chromium`).
- Shpock GraphQL-Schema kann sich ändern → Query in `shpock.py` ggf. anpassen.
- Gunicorn läuft mit `--workers 1`, da SQLite kein Multi-Process-Writing ohne WAL gut verträgt (WAL ist aktiviert).
