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
    ├── scheduler.py            # APScheduler: pro-Plattform-Crawl + Notify-Job (15 Min) + CronTrigger (Digest)
    ├── notifier.py             # SMTP E-Mail: gebündelter Alert (notify_pending) + Sofort (manual) + Digest
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
search_terms (id, term TEXT UNIQUE, enabled INT, created_at,
              max_price INTEGER NULL)

settings     (key TEXT PRIMARY KEY, value TEXT)

listings     (id, listing_id TEXT UNIQUE, platform, title, price,
              location, url, image_url, description, search_term,
              found_at, is_favorite INT DEFAULT 0,
              is_free INT DEFAULT 0, distance_km REAL,
              notes TEXT, potential_duplicate TEXT,
              notified_at TEXT)

geocache     (location_text TEXT PRIMARY KEY, lat REAL, lon REAL, cached_at)

dismissed_listings (listing_id TEXT PRIMARY KEY, dismissed_at TEXT)

profiles     (id INTEGER PRIMARY KEY, name TEXT NOT NULL, emoji TEXT DEFAULT '👤',
              last_seen_at TEXT, created_at TEXT)
```

**Migration**: Drei separate Migrations-Funktionen ergänzen fehlende Spalten in bestehenden DBs via `PRAGMA table_info` – keine Datenverluste bei Updates:
- `_migrate_listings()`: `is_favorite`, `is_free`, `distance_km`, `notes`, `potential_duplicate`, `notified_at`
- `_migrate_search_terms()`: `max_price`
- `_migrate_settings_values()`: Umbenennung `crawler_max_age_hours` → `display_max_age_hours`, Standort-Defaults

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
| `kleinanzeigen_interval` | `15` | Crawl-Intervall Minuten (Kleinanzeigen) |
| `shpock_interval` | `30` | Crawl-Intervall Minuten (Shpock) |
| `facebook_interval` | `60` | Crawl-Intervall Minuten (Facebook) |
| `vinted_interval` | `30` | Crawl-Intervall Minuten (Vinted) |
| `ebay_interval` | `60` | Crawl-Intervall Minuten (eBay) |
| `crawler_interval` | `15` | Globaler Fallback-Intervall (wird durch plattformspezifische Werte überschrieben) |
| `crawler_max_results` | `20` | Max. Ergebnisse pro Suche |
| `crawler_delay` | `2` | Pause zwischen Anfragen s |
| `crawler_blacklist` | `` | Ausschluss-Wörter, je Zeile eins |
| `display_max_age_hours` | `0` | Anzeigefilter: Anzeigen älter als X h ausblenden (0 = alle) |
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

### Max-Alter-Filter (Anzeigefilter)
`display_max_age_hours` filtert in `db.get_listings()` ältere Einträge aus der Anzeige heraus – die Daten bleiben in der DB. Auch per Dropdown im Dashboard wählbar (Letzte 3h / 6h / Heute / 48h).

### Pagination
`db.get_listings()` akzeptiert `limit` und `offset`. `/api/listings` liefert standardmäßig 30 Einträge. Das Dashboard lädt weitere Seiten per „Mehr laden"-Button (`loadMore()` in `index.html`). Server-seitig gerenderte Karten + JS-geladene Seiten fügen sich nahtlos zusammen.

### Sortierung
`db.get_listings(sort_by=...)` unterstützt: `date_desc` (Standard), `date_asc`, `price_asc`, `price_desc`, `distance_asc`. Preise werden via `CASE WHEN price GLOB '*[0-9]*'` auf numerischen Wert gecastet – Textwerte (k.A., Kostenlos) ergeben NULL und landen beim Sortieren immer am Ende. Favoriten stehen unabhängig von der Sortierung immer oben (`ORDER BY is_favorite DESC, ...`). `/api/listings?sort=` mit Whitelist-Validierung.

### Verfügbarkeits-Check
`checker.py.run_availability_check()` iteriert alle Anzeigen aus `db.get_all_listing_urls(min_age_minutes=60)` – Anzeigen jünger als 60 Minuten werden übersprungen. Sendet pro URL einen HEAD-Request (8s Timeout, 0,5s Delay). HTTP 404/410 → `db.delete_listing_by_listing_id()` löscht den Eintrag **inkl. Favoriten**. Hat einen `_running`-Guard (wie der Crawler) gegen parallele Ausführung. Wird vom Scheduler alle N Stunden ausgeführt (`availability_job`, `IntervalTrigger`). Einstellungen: `availability_check_enabled` (0/1), `availability_check_interval_hours` (Default 3). Manuell auslösbar über `POST /api/availability-check`.

### E-Mail-Benachrichtigung (gebündelt)
`notifier.notify_pending(settings)` läuft alle 15 Min. als `notify_job` im Scheduler. Es holt alle Listings mit `notified_at IS NULL` aus der DB (`db.get_unnotified_listings()`), sendet eine gruppierte HTML-E-Mail (nach Plattform → Suchbegriff mit Inhaltsverzeichnis, Gratis-Items grün hervorgehoben) und setzt `notified_at = NOW()` via `db.mark_listings_notified()`. Automatische Crawls rufen `notify()` nicht auf — nur der Job. Bei manuellem Crawl (`manual=True`) ruft `run_crawl()` direkt `notify()` auf, das ebenfalls `mark_listings_notified()` aufruft, damit der Job dieselben Listings nicht nochmals versendet.

### Radius 0 = kein Filter (Vinted & Shpock)
Beide Scraper lesen `vinted_radius` / `shpock_radius` via `_int()`; ist der Wert `0`, wird der Entfernungsfilter vollständig deaktiviert (kein Geocoding-Aufruf). Muster: `raw = _int(settings.get(..., "30")); self.radius_km = 30 if raw is None else raw`, Filter-Block: `if self._home and self.radius_km > 0:`.

### Suchbegriff-Filter im Dashboard (Mehrfachauswahl)
Jeder Suchbegriff in der linken Sidebar ist ein klickbarer `<button data-term="...">`. Klick togglet den Term im JS-`Set activeTerms` (hinzufügen/entfernen). Aktive Terms werden visuell hervorgehoben (blauer Text, fetter Font, `bg-brand-50`). Die Anzeigenliste wird via `/api/listings?term=a&term=b` gefiltert. Das Filter-Label zeigt alle aktiven Terme kommagetrennt. `clearFilter()` leert das Set und setzt alle Buttons zurück. Backend: `db.get_listings(search_terms: List[str])` — ein Term → `= ?`, mehrere → `IN (?, ...)`. Route: `request.args.getlist("term")`.

### Exclude-Filter (Live-Textfilter)
Eingabefeld „Begriffe ausschließen" in der Filter-Leiste. Eingaben werden mit 400 ms Debounce als `?exclude=...` an `/api/listings` übergeben. `db.get_listings(exclude_text=...)` filtert Anzeigen heraus, deren Titel **oder** Beschreibung den Begriff enthalten (`title NOT LIKE ? AND COALESCE(description,'') NOT LIKE ?`). Ein ×-Button leert das Feld und entfernt den Filter.

### Anzeige dauerhaft ausblenden (Dismiss)
`POST /listings/<id>/dismiss` ruft `db.dismiss_listing(db_id)` auf: liest `listing_id`-String, trägt ihn in `dismissed_listings`-Tabelle ein, löscht das Listing. `db.save_listing()` prüft via `is_dismissed(listing_id)` vor dem INSERT – schlägt fehl (return `False`) wenn bereits dismissed. Damit taucht eine ausgeblendete Anzeige beim nächsten Crawl nie wieder auf. Im Frontend: ✕-Button oben links auf jeder Karte (AJAX, entfernt Karte aus DOM).

### Suchbegriff-Löschen löscht auch Anzeigen
`db.delete_search_term(term_id)` holt zuerst den Text des Suchbegriffs, löscht dann alle `listings` mit `search_term = <text>`, danach den Suchbegriff selbst – alles in einer Transaktion.

### Notizfeld pro Anzeige
`POST /listings/<id>/note` (JSON `{"note": "..."}`) ruft `db.update_listing_note(db_id, note)` auf. Leerstring → `NULL`. Im Modal editierbar (Textarea + Auto-Save). Karten mit Notiz zeigen ein 💬-Badge.

### Duplikat-Erkennung (plattformübergreifend)
`db.find_duplicate_platform(title, platform)` sucht nach einem Listing mit identischem Titelanfang (LOWER(SUBSTR(title,1,50))) auf einer anderen Plattform (letzte 30 Tage, min. 5 Zeichen). Wird in `save_listing()` nach jedem INSERT aufgerufen. Treffer werden in `listings.potential_duplicate` gespeichert. Im Dashboard als Amber-Badge „📋 auch auf Shpock" angezeigt.

### Per-Term Preisschwelle
`search_terms.max_price INTEGER NULL` speichert eine optionale Preisobergrenze pro Suchbegriff. In `run_crawl()` wird `term_row.get("max_price")` gegen `price_within_limit()` aus `scrapers/base.py` geprüft – zu teure Anzeigen werden vor dem Speichern herausgefiltert. In der Sidebar per Inline-Edit setzbar (Stift-Icon → Eingabefeld → ENTER). Route: `POST /terms/<id>/max-price`.

### Mehrbenutzer-Profile
`profiles`-Tabelle speichert `name`, `emoji` und `last_seen_at` pro Person. Wenn Profile existieren und kein Profil in der Flask-Session → automatischer Redirect zu `/profiles/select` (Netflix-Stil). Beim Auswählen eines Profils wird `session["profile_last_seen"]` auf den alten `last_seen_at`-Wert gesetzt, danach `last_seen_at` in DB auf `NOW()` aktualisiert. `is_new`-Flag im Dashboard und in `/api/listings`: `found_at > profile_last_seen`. **Suchbegriffe sind global geteilt**, kein Per-Profil-Filtering. Verwaltung im neuen Settings-Tab „Profile" (anlegen, bearbeiten via AJAX, löschen via AJAX). Aktives Profil + Wechsel-Button in der Navbar.

### Settings-Seite: 3-Tab-Layout
Die Einstellungsseite ist in vier Tabs unterteilt: **Plattformen**, **Benachrichtigungen**, **Crawler & Daten**, **Profile**. `switchTab(tabId)` blendet Panels ein/aus und setzt `active-tab`-CSS. Aktiver Tab wird in `localStorage` gespeichert.

### Settings-Seite: UX-Verbesserungen
- **Plattform-Dimming**: Deaktivierte Plattformblöcke werden visuell gedimmt (`data-platform-section` / `data-platform-fields`, `initPlatformDimming()`).
- **Sticky Save-Button**: Speichern-Button klebt am Seitenende (`sticky bottom-4 z-20`).
- **Unsaved-Changes-Warnung**: `beforeunload`-Handler solange `_formDirty = true`.
- **Inline-Validierung**: `showFieldError()` zeigt Fehler direkt am Feld, wechselt zum richtigen Tab.
- **Test-Buttons**: Pro Plattform ein „Verbindung testen"-Button ruft `POST /api/test-scraper` auf und zeigt Ergebnis inline.

### Dashboard: Filter-Panel
Filterbereich ist ein- und ausklappbar (`toggleFilterPanel()`). Anzahl aktiver Filter wird als Badge am Toggle-Button angezeigt. Zustand wird in `localStorage` gespeichert.

### Dashboard: Relative Zeitangaben
`relativeTime(isoStr)` rechnet ISO-Timestamps in „vor 2h" / „vor 30 Min" um. Wird via `initRelativeTimes()` auf alle `.found-at-ts[data-found-at]`-Elemente angewendet.

### Dashboard: Listing-Modal
Klick auf eine Karte öffnet `#detail-modal` mit Vollbild-Details (Bild, Preis, Standort, Beschreibung, Notiz-Textarea). Daten kommen aus `listingsCache` (JS-Map, aus Jinja-`<script>`-Block befüllt). `handleCardClick(event, id)` unterscheidet zwischen Karte und Buttons.

### Dashboard: Plattform-Filter & Status-Bar
`loadPlatformOptions()` befüllt das Plattform-Dropdown aus `GET /api/platforms` (nur tatsächlich vorhandene Plattformen). `updatePlatformCounts()` zeigt „KA 120 · Shp 45" unter dem Gesamt-Zähler.

## Wichtige Konventionen

- **Scraper-Interface**: Jeder Scraper hat `__init__(self, settings: dict)` und `search(self, term: str, max_results: int) -> List[Listing]`. `settings` ist das komplette Dict aus `db.get_settings()`.
- **Neuen Scraper hinzufügen**: Neue Klasse in `app/scrapers/`, in `crawler.py` in die Scraper-Liste eintragen, in `routes.py` und `settings.html` entsprechende Felder ergänzen.
- **Kein ORM**: Alle DB-Zugriffe direkt mit `sqlite3` in `database.py`. Neue Abfragen dort als Funktion anlegen.
- **Kein JS-Build**: Tailwind via CDN. Kein npm. JS direkt in den Templates als `<script>`-Blöcke.
- **Thread-Safety**: `crawler.py` und `checker.py` nutzen je ein eigenes `threading.Lock` + `_running`-Flag. Nie direkt `run_crawl()` aufrufen – immer `run_crawl_async()`.
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
|--------|-----|--------------|
| GET | `/` | Dashboard |
| POST | `/terms` | Suchbegriff hinzufügen (`form: term`) |
| POST | `/terms/<id>/delete` | Suchbegriff löschen |
| POST | `/terms/<id>/toggle` | Aktivieren / Deaktivieren |
| GET | `/settings` | Einstellungsseite |
| POST | `/settings` | Einstellungen speichern |
| POST | `/listings/<id>/favorite` | Favorit toggeln (JSON) |
| POST | `/api/crawl` | Crawl manuell starten (JSON) |
| GET | `/api/status` | Crawler-Status als JSON |
| GET | `/api/listings` | Anzeigen als JSON (`?term=`, `?platform=`, `?limit=30`, `?offset=0`, `?favorites=1`, `?free=1`, `?max_age=`, `?max_distance=`, `?sort=date_desc`, `?exclude=`) |
| GET | `/api/stats` | Preisstatistik pro Suchbegriff (JSON) |
| POST | `/listings/<id>/dismiss` | Anzeige dauerhaft ausblenden (JSON) |
| POST | `/listings/<id>/note` | Notiz setzen/löschen (JSON: `{"note": "..."}`) |
| POST | `/terms/<id>/max-price` | Preis-Schwelle für Term setzen (JSON: `{"max_price": N}`) |
| GET | `/api/platforms` | Distinct Plattformen der gespeicherten Anzeigen (JSON Array) |
| POST | `/api/test-scraper` | Scraper-Verbindung testen (JSON: `{"platform": "kleinanzeigen"}`) |
| POST | `/api/clear-listings-by-age` | Anzeigen löschen + dismissen die älter als `hours` sind (JSON body: `{"hours": N}`) |
| GET | `/profiles/select` | Profil-Auswahl-Seite (nur wenn Profile existieren) |
| POST | `/profiles/select/<id>` | Profil aktivieren, `last_seen_at` in DB aktualisieren, Session setzen |
| POST | `/profiles/logout` | Session leeren, zurück zur Profilauswahl |
| POST | `/profiles` | Neues Profil anlegen (form: `name`, `emoji`) |
| POST | `/profiles/<id>/update` | Profil umbenennen/Emoji ändern (JSON: `{"name": "...", "emoji": "..."}`) |
| POST | `/profiles/<id>/delete` | Profil löschen (JSON response) |

## Bekannte Einschränkungen

- Kleinanzeigen.de ändert gelegentlich seine HTML-Selektoren → CSS-Selektoren in `kleinanzeigen.py._parse()` ggf. anpassen.
- Facebook Marketplace benötigt interaktiven einmaligen Login und Playwright (`playwright install chromium`).
- Shpock GraphQL-Schema kann sich ändern → Query in `shpock.py` ggf. anpassen. Shpock ignoriert den Location-Filter ohne Session – Radius-Filterung erfolgt client-seitig via Geocoding.
- Vinted benötigt beim Start einen anonymen Session-Cookie (wird automatisch via `_authenticate()` geholt). Bei 401 erfolgt ein automatischer Retry.
- Nominatim-Geocoding funktioniert nur wenn der Standorttext in der Anzeige eindeutig genug ist. Bei unklaren Ortsangaben wird kein Treffer zurückgegeben.
- Gunicorn läuft mit `--workers 1`, da SQLite kein Multi-Process-Writing ohne WAL gut verträgt (WAL ist aktiviert).
