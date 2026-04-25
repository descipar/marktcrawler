# CLAUDE.md – Baby-Crawler

Dieses Dokument beschreibt die Architektur und Konventionen des Projekts für KI-Assistenten.

## Projektübersicht

Web-App zum automatisierten Durchsuchen von Kleinanzeigen-Plattformen (Kleinanzeigen.de, Shpock, Facebook Marketplace) nach Babysachen. Neue Treffer werden per E-Mail gemeldet. Verwaltung über eine Flask-basierte Admin-UI.

## Tech-Stack

- **Backend**: Python 3.12, Flask 3, APScheduler 3
- **Datenbank**: SQLite (via `sqlite3` Standardbibliothek, kein ORM)
- **Scraping**: `requests` + `BeautifulSoup`/`lxml` (Kleinanzeigen), GraphQL-API (Shpock), Playwright (Facebook)
- **Geocoding**: Nominatim (OpenStreetMap), Ergebnisse in `geocache`-Tabelle gecacht, 1 req/s Rate-Limit
- **Frontend**: Jinja2-Templates, Tailwind CSS (CDN), Vanilla JS (kein Build-Step)
- **Deployment**: Docker + docker-compose, Gunicorn 1 Worker

## Verzeichnisstruktur

```
baby-crawler-v2/
├── run.py                      # Einstiegspunkt (Flask dev server + load_dotenv)
├── .env                        # Lokale Entwicklung: DATA_DIR=./data
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── data/                       # Persistentes Volume (SQLite-DB, FB-Session)
└── app/
    ├── __init__.py             # Flask App Factory, initialisiert DB + Scheduler
    ├── database.py             # Gesamte SQLite-Schicht (kein ORM), Migration
    ├── routes.py               # Alle Flask-Routen + REST-API (Blueprint "main")
    ├── crawler.py              # Crawl-Orchestrierung, threading.Lock, run_crawl_async()
    ├── scheduler.py            # APScheduler: IntervalTrigger (Crawl) + CronTrigger (Digest)
    ├── notifier.py             # SMTP E-Mail: Sofort-Alert + Tages-Digest
    ├── geo.py                  # Haversine-Formel + Nominatim-Geocoding mit DB-Cache
    ├── scrapers/
    │   ├── base.py             # Listing-Dataclass (gemeinsame Datenstruktur)
    │   ├── kleinanzeigen.py    # requests + BeautifulSoup
    │   ├── shpock.py           # GraphQL-API POST
    │   └── facebook.py        # Playwright headless (optional)
    └── templates/
        ├── base.html           # Navbar, Flash-Messages, Tailwind-Setup
        ├── index.html          # Dashboard: Suchbegriffe + Anzeigen-Grid + Live-Status
        └── settings.html      # Einstellungsformular (alle Plattformen + Features)
```

## Datenbankschema

Vier Tabellen in `$DATA_DIR/baby_crawler.db` (Standard: `/data/`):

```sql
search_terms (id, term TEXT UNIQUE, enabled INT, created_at)

settings     (key TEXT PRIMARY KEY, value TEXT)

listings     (id, listing_id TEXT UNIQUE, platform, title, price,
              location, url, image_url, description, search_term,
              found_at, is_favorite INT DEFAULT 0,
              is_free INT DEFAULT 0, distance_km REAL)

geocache     (location_text TEXT PRIMARY KEY, lat REAL, lon REAL, cached_at)
```

**Migration**: `database.py._migrate_listings()` ergänzt fehlende Spalten in bestehenden DBs via `PRAGMA table_info` – keine Datenverluste bei Updates.

### Alle Settings-Keys

| Key | Default | Beschreibung |
|-----|---------|-------------|
| `kleinanzeigen_enabled` | `1` | Plattform aktiv |
| `kleinanzeigen_max_price` | `100` | Max. Preis € |
| `kleinanzeigen_location` | `dortmund` | Standort-Slug |
| `kleinanzeigen_radius` | `30` | Radius km |
| `shpock_enabled` | `1` | Plattform aktiv |
| `shpock_max_price` | `80` | Max. Preis € |
| `shpock_location` | `München` | Stadtname für Geocoding |
| `shpock_latitude` | `48.1351` | Standort lat (Fallback) |
| `shpock_longitude` | `11.5820` | Standort lon (Fallback) |
| `shpock_radius` | `30` | Radius km (client-seitig gefiltert) |
| `facebook_enabled` | `0` | Plattform aktiv |
| `facebook_max_price` | `80` | Max. Preis € |
| `facebook_location` | `München` | Standort |
| `vinted_enabled` | `0` | Plattform aktiv |
| `vinted_max_price` | `80` | Max. Preis € |
| `vinted_location` | `München` | Stadtname für Geocoding |
| `vinted_radius` | `30` | Radius km (client-seitig gefiltert) |
| `ebay_enabled` | `0` | Plattform aktiv |
| `ebay_max_price` | `80` | Max. Preis € |
| `ebay_location` | `München` | PLZ oder Stadtname (`_stpos`) |
| `ebay_radius` | `30` | Radius km (`_sadis`) |
| `email_enabled` | `0` | E-Mail aktiv |
| `email_subject_alert` | `🍼 Baby-Crawler: {n} neue Anzeige(n) gefunden!` | Betreff Sofort-Alert (`{n}` = Anzahl) |
| `email_subject_digest` | `🍼 Baby-Crawler Tages-Digest: {n} Anzeige(n) heute` | Betreff Digest (`{n}` = Anzahl) |
| `email_smtp_server` | `smtp.gmail.com` | SMTP Host |
| `email_smtp_port` | `587` | SMTP Port |
| `email_sender` | `` | Absender |
| `email_password` | `` | App-Passwort |
| `email_recipient` | `` | Empfänger (kommagetrennt) |
| `crawler_interval` | `15` | Crawl-Intervall Minuten |
| `crawler_max_results` | `20` | Max. Ergebnisse pro Suche |
| `crawler_delay` | `2` | Pause zwischen Anfragen s |
| `crawler_blacklist` | `` | Ausschluss-Wörter, je Zeile eins |
| `crawler_max_age_hours` | `0` | Max. Alter h (0 = alle) |
| `digest_enabled` | `0` | Tages-Digest aktiv |
| `digest_time` | `19:00` | Uhrzeit für Digest HH:MM |
| `home_latitude` | `` | Heimstandort lat (für Distanz) |
| `home_longitude` | `` | Heimstandort lon (für Distanz) |

## Features

### Blacklist
`crawler.py._is_blacklisted()` prüft Titel + Beschreibung gegen alle Zeilen aus `crawler_blacklist`. Groß-/Kleinschreibung wird ignoriert. Blacklistete Anzeigen werden still übersprungen (kein Speichern, keine Benachrichtigung).

### Gratis-Erkennung
`crawler.py._is_free()` erkennt Gratisanzeigen anhand von Preis-Regex (`0\s*€`, `Kostenlos`, `Gratis`) und Keywords im Titel (`zu verschenken`, `gratis`, etc.). Ein echter Preis > 0 hat immer Vorrang – Text-Keywords in der Beschreibung (z.B. „gratis Zubehör dabei") führen dann nicht zu einem False-Positive. Setzt `Listing.is_free = True`. Im Dashboard mit 🎁-Badge gekennzeichnet.

### Entfernungsberechnung
`geo.py.distance_to_home()` geocodiert den Standort der Anzeige via Nominatim (OSM), berechnet die Distanz zum Heimstandort mit der Haversine-Formel und speichert das Ergebnis in `listings.distance_km`. Geocoding-Ergebnisse werden in der `geocache`-Tabelle gecacht (kein doppelter API-Aufruf). Rate-Limit: 1 req/s.

### Tages-Digest
Täglich zur konfigurierten Uhrzeit (CronTrigger) sendet `notifier.send_digest()` alle heute gefundenen Anzeigen als HTML-E-Mail. Unabhängig von Sofort-Benachrichtigungen.

### Favoriten
`POST /listings/<id>/favorite` (AJAX) toggelt `is_favorite`. Favoriten werden beim automatischen `clear_old_listings()` nicht gelöscht. Dashboard-Filter: `?favorites=1`.

### Preisstatistik
`GET /api/stats` liefert Avg/Min/Max-Preis und Gratis-Zähler pro Suchbegriff. Im Dashboard als aufklappbare Tabelle.

### Max-Alter-Filter
`crawler_max_age_hours` filtert in `db.get_listings()` ältere Einträge heraus. Auch per Dropdown im Dashboard wählbar (Letzte 3h / 6h / Heute / 48h).

### Pagination
`db.get_listings()` akzeptiert `limit` und `offset`. `/api/listings` liefert standardmäßig 30 Einträge. Das Dashboard lädt weitere Seiten per „Mehr laden"-Button (`loadMore()` in `index.html`). Server-seitig gerenderte Karten + JS-geladene Seiten fügen sich nahtlos zusammen.

### Sortierung
`db.get_listings(sort_by=...)` unterstützt: `date_desc` (Standard), `date_asc`, `price_asc`, `price_desc`, `distance_asc`. Preise werden via `CASE WHEN price GLOB '*[0-9]*'` auf numerischen Wert gecastet – Textwerte (k.A., Kostenlos) ergeben NULL und landen beim Sortieren immer am Ende. Favoriten stehen unabhängig von der Sortierung immer oben (`ORDER BY is_favorite DESC, ...`). `/api/listings?sort=` mit Whitelist-Validierung.

### E-Mail bei manuellem Crawl
`run_crawl_async(manual=True)` wird vom `/api/crawl`-Endpoint aufgerufen. `run_crawl(manual=True)` reicht `force=True` an `notify()` weiter, das dann das Rate-Limit überspringt. Automatische Crawls übergeben `force=False` (Standard) — das Rate-Limit gilt weiterhin.

## Wichtige Konventionen

- **Scraper-Interface**: Jeder Scraper hat `__init__(self, settings: dict)` und `search(self, term: str, max_results: int) -> List[Listing]`. `settings` ist das komplette Dict aus `db.get_settings()`.
- **Neuen Scraper hinzufügen**: Neue Klasse in `app/scrapers/`, in `crawler.py` in die Scraper-Liste eintragen, in `routes.py` und `settings.html` entsprechende Felder ergänzen.
- **Kein ORM**: Alle DB-Zugriffe direkt mit `sqlite3` in `database.py`. Neue Abfragen dort als Funktion anlegen.
- **Kein JS-Build**: Tailwind via CDN. Kein npm. JS direkt in den Templates als `<script>`-Blöcke.
- **Thread-Safety**: `crawler.py` nutzt `threading.Lock` + globales `_running`-Flag. Nie direkt `run_crawl()` aufrufen – immer `run_crawl_async()`.
- **Settings-Checkboxen**: In HTML-Forms senden Checkboxen keinen Wert wenn nicht angehakt. `routes.py → save_settings()` behandelt das explizit mit `"1" if request.form.get(key) else "0"`.
- **Datenbankpfad**: `DATA_DIR`-Umgebungsvariable (Default `/data`). Lokal via `.env`: `DATA_DIR=./data`.

## Lokale Entwicklung

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# .env bereits vorhanden mit DATA_DIR=./data
python run.py                     # startet auf http://localhost:5000
```

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
| POST | `/listings/<id>/favorite` | Favorit toggeln (JSON) |
| POST | `/api/crawl` | Crawl manuell starten (JSON) |
| GET | `/api/status` | Crawler-Status als JSON |
| GET | `/api/listings` | Anzeigen als JSON (`?term=`, `?platform=`, `?limit=30`, `?offset=0`, `?favorites=1`, `?free=1`, `?max_age=`, `?max_distance=`) |
| GET | `/api/stats` | Preisstatistik pro Suchbegriff (JSON) |

## Bekannte Einschränkungen

- Kleinanzeigen.de ändert gelegentlich seine HTML-Selektoren → CSS-Selektoren in `kleinanzeigen.py._parse()` ggf. anpassen.
- Facebook Marketplace benötigt interaktiven einmaligen Login und Playwright (`playwright install chromium`).
- Shpock GraphQL-Schema kann sich ändern → Query in `shpock.py` ggf. anpassen. Shpock ignoriert den Location-Filter ohne Session – Radius-Filterung erfolgt client-seitig via Geocoding.
- Vinted benötigt beim Start einen anonymen Session-Cookie (wird automatisch via `_authenticate()` geholt). Bei 401 erfolgt ein automatischer Retry.
- Nominatim-Geocoding funktioniert nur wenn der Standorttext in der Anzeige eindeutig genug ist. Bei unklaren Ortsangaben wird kein Treffer zurückgegeben.
- Gunicorn läuft mit `--workers 1`, da SQLite kein Multi-Process-Writing ohne WAL gut verträgt (WAL ist aktiviert).
