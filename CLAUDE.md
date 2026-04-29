# CLAUDE.md – Marktcrawler

Dieses Dokument beschreibt die Architektur und Konventionen des Projekts für KI-Assistenten.

## Projektübersicht

Web-App zum automatisierten Durchsuchen von Kleinanzeigen-Plattformen (Kleinanzeigen.de, Shpock, Vinted, eBay, Willhaben.at, markt.de, Facebook Marketplace) nach Babysachen. Neue Treffer werden per E-Mail gemeldet. Verwaltung über eine Flask-basierte Admin-UI.

## Tech-Stack

- **Backend**: Python 3.12, Flask 3, APScheduler 3
- **Datenbank**: SQLite (via `sqlite3` Standardbibliothek, kein ORM)
- **Scraping**: `requests` + `BeautifulSoup`/`lxml` (Kleinanzeigen, markt.de), GraphQL-API (Shpock), JSON-API (Vinted, Willhaben `__NEXT_DATA__`), Playwright (Facebook)
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
    ├── __init__.py             # Flask App Factory, initialisiert DB + Scheduler; SECRET_KEY-Persistenz
    ├── database/               # SQLite-Schicht (kein ORM), versioniertes Migrations-Framework
    │   ├── __init__.py         # Re-Exports aller öffentlichen Symbole (Rückwärtskompatibilität)
    │   ├── core.py             # DB_PATH, get_db()/_db(), init_db(), Migrations, utcnow()
    │   ├── settings.py         # get_settings(), set_setting(), save_settings()
    │   ├── search_terms.py     # get_search_terms(), create/delete/toggle/update_max_price
    │   ├── listings.py         # save_listing(), get_listings(), clear_old_listings(), claim_unnotified_listings()
    │   ├── geocache.py         # get_geocache(), save_geocache() – Keys lowercase-normalisiert
    │   ├── profiles.py         # get_profiles(), create/update/delete_profile()
    │   └── stats.py            # get_price_stats(), get_platform_counts(), log_crawl_run()
    ├── routes/                 # Flask-Routen (Blueprint "main")
    │   ├── __init__.py         # Blueprint-Definition; importiert views, api, profiles
    │   ├── views.py            # Dashboard, Settings, Favoriten, Dismiss, Notiz (HTML-Routen)
    │   ├── api.py              # REST-API (/api/*)
    │   ├── profiles.py         # /profiles/*-Routen
    │   └── _helpers.py         # PLATFORMS, build_platform_stats(), build_platform_max_ages()
    ├── crawler.py              # Crawl-Orchestrierung, threading.Lock, run_crawl_async()
    ├── scheduler.py            # APScheduler: pro-Plattform-Crawl + Notify-Job (15 Min) + CronTrigger (Digest); restart-resilient via start_date
    ├── notifier.py             # SMTP E-Mail: gebündelter Alert (notify_pending) + Sofort (manual) + Digest
    ├── ai.py                   # KI-Assistent: Verkäufer-Anfragetext, VB-Preisvorschlag (Claude/OpenAI)
    ├── geo.py                  # Haversine-Formel + Nominatim-Geocoding mit DB-Cache
    ├── scrapers/
    │   ├── base.py             # Listing-Dataclass (gemeinsame Datenstruktur)
    │   ├── kleinanzeigen.py    # requests + BeautifulSoup
    │   ├── shpock.py           # GraphQL-API POST
    │   ├── vinted.py           # REST-API mit Session-Cookie; Altersfilter via created_at_ts
    │   ├── ebay.py             # requests + BeautifulSoup; URL-Encoding mit quote_plus
    │   ├── willhaben.py        # __NEXT_DATA__ JSON-Parsing; PayLivery-Filter; Haversine-Radius
    │   ├── markt.py            # requests + BeautifulSoup; Umlaut-Slug für Stadt-URL
    │   └── facebook.py         # Playwright headless (optional)
    └── templates/
        ├── base.html           # Navbar, Flash-Messages, Tailwind-Setup
        ├── index.html          # Dashboard: Suchbegriffe + Anzeigen-Grid + Live-Status
        ├── settings.html       # Einstellungsformular (5 Tabs)
        ├── profiles_select.html # Profil-Auswahl (Netflix-Stil)
        └── _listing_card.html  # Anzeigenkarte (Jinja2-Partial)
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

**Migration**: Versioniertes Migrations-Framework mit `_migrations`-Tracking-Tabelle. `_run_pending_migrations(conn)` führt jede Migration genau einmal aus (Idempotenz via Namens-Check). Danach `_ensure_indexes(conn)` für Performance-Indexes. Keine Datenverluste bei Updates:
- `v1_settings_rename`: Umbenennung `crawler_max_age_hours` → `display_max_age_hours`, Standort-Defaults
- `v2_listings_columns`: `is_favorite`, `is_free`, `distance_km`, `notes`, `potential_duplicate`, `notified_at`
- `v3_search_terms_max_price`: `max_price`
- `v4_backfill_notified_at`: setzt `notified_at = NOW()` für alle bestehenden NULL-Einträge — verhindert, dass alle Altanzeigen beim ersten `notify_pending()`-Aufruf als „neu" gelten und eine Massen-E-Mail auslösen

**Performance-Indexes** (angelegt nach Migrations, via `_ensure_indexes()`): `platform`, `search_term`, `found_at`, `is_favorite`, `notified_at`, kombinierter Index `(platform, found_at)`.

### Alle Settings-Keys

| Key | Default | Beschreibung |
|-----|---------|-------------|
| `kleinanzeigen_enabled` | `1` | Plattform aktiv |
| `kleinanzeigen_max_price` | `100` | Max. Preis € |
| `kleinanzeigen_location` | `dortmund` | Standort-Slug |
| `kleinanzeigen_radius` | `30` | Radius km |
| `kleinanzeigen_max_age_hours` | `0` | Max. Anzeigedauer in Stunden (0 = kein Filter) |
| `shpock_enabled` | `1` | Plattform aktiv |
| `shpock_max_price` | `80` | Max. Preis € |
| `shpock_location` | `München` | Stadtname für Geocoding |
| `shpock_latitude` | `48.1351` | Standort lat (Fallback) |
| `shpock_longitude` | `11.5820` | Standort lon (Fallback) |
| `shpock_radius` | `30` | Radius km (client-seitig gefiltert) |
| `shpock_max_age_hours` | `0` | Max. Anzeigedauer in Stunden (0 = kein Filter) |
| `facebook_enabled` | `0` | Plattform aktiv |
| `facebook_max_price` | `80` | Max. Preis € |
| `facebook_location` | `München` | Standort |
| `facebook_max_age_hours` | `0` | Max. Anzeigedauer in Stunden (0 = kein Filter) |
| `vinted_enabled` | `0` | Plattform aktiv |
| `vinted_max_price` | `80` | Max. Preis € |
| `vinted_location` | `München` | Stadtname für Geocoding |
| `vinted_radius` | `30` | Radius km (client-seitig gefiltert) |
| `vinted_max_age_hours` | `48` | Max. Anzeigedauer in Stunden (Vinted-Default 48h) |
| `ebay_enabled` | `0` | Plattform aktiv |
| `ebay_max_price` | `80` | Max. Preis € |
| `ebay_location` | `München` | PLZ oder Stadtname (`_stpos`) |
| `ebay_radius` | `30` | Radius km (`_sadis`) |
| `ebay_max_age_hours` | `0` | Max. Anzeigedauer in Stunden (0 = kein Filter) |
| `willhaben_enabled` | `0` | Plattform aktiv |
| `willhaben_max_price` | `100` | Max. Preis € |
| `willhaben_location` | `München` | Stadtname (nur bei PayLivery deaktiviert) |
| `willhaben_radius` | `50` | Radius km (nur bei PayLivery deaktiviert) |
| `willhaben_paylivery_only` | `1` | Nur Versand-Angebote (PayLivery); deaktiviert Radius-Filter |
| `willhaben_interval` | `30` | Crawl-Intervall Minuten |
| `willhaben_max_age_hours` | `0` | Max. Anzeigedauer in Stunden (0 = kein Filter) |
| `marktde_enabled` | `0` | Plattform aktiv |
| `marktde_max_price` | `100` | Max. Preis € |
| `marktde_location` | `München` | Stadtname für URL-Slug (Umlaute werden konvertiert) |
| `marktde_radius` | `50` | Radius km (URL-Parameter) |
| `marktde_interval` | `60` | Crawl-Intervall Minuten |
| `marktde_max_age_hours` | `0` | Max. Anzeigedauer in Stunden (0 = kein Filter) |
| `email_enabled` | `0` | E-Mail aktiv |
| `email_subject_alert` | `🔍 Marktcrawler: {n} neue Anzeige(n) gefunden!` | Betreff Sofort-Alert (`{n}` = Anzahl) |
| `email_subject_digest` | `🔍 Marktcrawler Tages-Digest: {n} Anzeige(n) heute` | Betreff Digest (`{n}` = Anzahl) |
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
| `willhaben_interval` | `30` | Crawl-Intervall Minuten (Willhaben) |
| `marktde_interval` | `60` | Crawl-Intervall Minuten (markt.de) |
| `crawler_interval` | `15` | Globaler Fallback-Intervall (wird durch plattformspezifische Werte überschrieben) |
| `crawler_max_results` | `20` | Max. Ergebnisse pro Suche |
| `crawler_delay` | `2` | Pause zwischen Anfragen s |
| `crawler_blacklist` | `` | Ausschluss-Wörter, je Zeile eins |
| `display_max_age_hours` | `0` | Anzeigefilter: Anzeigen älter als X h ausblenden (0 = alle) |
| `digest_enabled` | `0` | Tages-Digest aktiv |
| `digest_time` | `19:00` | Uhrzeit für Digest HH:MM |
| `server_url` | `` | Basis-URL des Dashboards für E-Mail-Links (z.B. `http://192.168.1.10:5000`); leer = automatische Erkennung (funktioniert in Docker nicht zuverlässig) |
| `home_latitude` | `` | Heimstandort lat (für Distanz) |
| `home_longitude` | `` | Heimstandort lon (für Distanz) |
| `ai_enabled` | `0` | KI-Assistent aktiv |
| `ai_api_key` | `` | Anthropic/OpenAI API-Key |
| `ai_model` | `claude-haiku-4-5-20251001` | Modellname |
| `ai_base_url` | `` | Leer = Cloud-API; `http://ollama:11434/v1` = Ollama |
| `ai_prompt_hints` | `` | Persönliche Hinweise für jeden generierten Anfragetext |

## Features

### Blacklist
`crawler.py._is_blacklisted()` prüft Titel + Beschreibung gegen alle Zeilen aus `crawler_blacklist`. Groß-/Kleinschreibung wird ignoriert. Blacklistete Anzeigen werden still übersprungen (kein Speichern, keine Benachrichtigung).

### Mehrwort-Suchbegriff-Filter (AND-Logik mit Wortgrenzen)
`crawler.py._matches_all_words(listing, term)` stellt sicher, dass bei Mehrwort-Begriffen (z.B. „baby werder") **alle** Wörter in Titel oder Beschreibung vorkommen. Nutzt `\b`-Regex (Wortgrenzen) statt Substring-Suche — verhindert False-Positives wie „werder" → „Schwerder". Einwort-Begriffe werden nicht geprüft. Wird vor dem Blacklist-Check ausgeführt; nicht passende Anzeigen werden verworfen.

### Sprachfilter
`crawler.py._is_lang_allowed(listing, allowed_langs)` erkennt die Sprache einer Anzeige via `langdetect` und filtert nicht erlaubte Sprachen heraus. Settings: `crawler_lang_filter_enabled` (0/1), `crawler_lang_filter_langs` (kommagetrennt, Default `de`). Texte kürzer als 20 Zeichen und Erkennungsfehler (LangDetectException, ImportError) werden durchgelassen. Besonders nützlich bei Vinted (viele FR/NL-Anzeigen).

### Auto-Cleanup nicht passender Anzeigen
`db.cleanup_mismatched_listings()` in `database/listings.py` löscht alle Anzeigen, deren Titel+Beschreibung nicht alle Wörter ihres Suchbegriffs (AND-Logik mit Wortgrenzen) enthalten, und trägt sie in `dismissed_listings` ein. Läuft einmalig als v9-Migration. Manuell: `POST /api/cleanup-mismatched` (Button im Daten-Tab der Einstellungen).

### Gratis-Erkennung
`crawler.py._is_free()` erkennt Gratisanzeigen anhand von Preis-Regex (`0\s*€`, `Kostenlos`, `Gratis`) und Keywords im Titel (`zu verschenken`, `gratis`, etc.). Ein echter Preis > 0 hat immer Vorrang – Text-Keywords in der Beschreibung (z.B. „gratis Zubehör dabei") führen dann nicht zu einem False-Positive. Setzt `Listing.is_free = True`. Im Dashboard mit 🎁-Badge gekennzeichnet.

### Entfernungsberechnung
`geo.py.distance_to_home()` geocodiert den Standort der Anzeige via Nominatim (OSM), berechnet die Distanz zum Heimstandort mit der Haversine-Formel und speichert das Ergebnis in `listings.distance_km`. Geocoding-Ergebnisse werden in der `geocache`-Tabelle gecacht (kein doppelter API-Aufruf). Rate-Limit: 1 req/s.

### Tages-Digest
Täglich zur konfigurierten Uhrzeit (CronTrigger) sendet `notifier.send_digest()` alle heute gefundenen Anzeigen als HTML-E-Mail. Unabhängig von Sofort-Benachrichtigungen.

### Favoriten
`POST /listings/<id>/favorite` (AJAX) toggelt `is_favorite`. Favoriten werden beim automatischen `clear_old_listings()` nicht gelöscht. Dashboard-Filter: `?favorites=1`.

### Preisstatistik
`GET /api/stats` liefert Avg/Min/Max-Preis und Gratis-Zähler pro Suchbegriff. Angezeigt auf der Info-Seite (`/info`) unterhalb der globalen Preis-Kacheln als Tabelle nach Suchbegriff aufgeschlüsselt.

### Max-Alter-Filter (Anzeigefilter)
`display_max_age_hours` filtert in `db.get_listings()` ältere Einträge aus der Anzeige heraus – die Daten bleiben in der DB. Auch per Dropdown im Dashboard wählbar (Letzte 3h / 6h / Heute / 48h).

### Pagination
`db.get_listings()` akzeptiert `limit` und `offset`. `/api/listings` liefert standardmäßig 30 Einträge. Das Dashboard lädt weitere Seiten per „Mehr laden"-Button (`loadMore()` in `index.html`). Server-seitig gerenderte Karten + JS-geladene Seiten fügen sich nahtlos zusammen.

### Sortierung
`db.get_listings(sort_by=...)` unterstützt: `date_desc` (Standard), `date_asc`, `price_asc`, `price_desc`, `distance_asc`. Preise werden via `CASE WHEN price GLOB '*[0-9]*'` auf numerischen Wert gecastet – Textwerte (k.A., Kostenlos) ergeben NULL und landen beim Sortieren immer am Ende. Favoriten stehen unabhängig von der Sortierung immer oben (`ORDER BY is_favorite DESC, ...`). `/api/listings?sort=` mit Whitelist-Validierung.

### Verfügbarkeits-Check
`checker.py.run_availability_check()` prüft Anzeigen parallel (ThreadPoolExecutor, Default 5 Worker) via HEAD-Request (6s Timeout). HTTP 404/410 → `db.delete_listing_by_listing_id()` löscht den Eintrag **inkl. Favoriten**. Anzeigen jünger als 60 Min. werden übersprungen. Re-Check-Throttling: jede Anzeige höchstens alle `availability_recheck_hours` Stunden (Default 48h) erneut prüfen — `availability_checked_at` pro Listing in DB gespeichert (v8-Migration). Hat einen `_running`-Guard gegen parallele Ausführung. Einstellungen: `availability_check_enabled`, `availability_check_interval_hours` (Default 3), `availability_check_workers` (Default 5), `availability_recheck_hours` (Default 48). Manuell auslösbar über `POST /api/availability-check`.

### Restart-resilientes Scheduling
Alle Interval-Jobs (Plattform-Crawls, Availability-Check) berechnen beim Start ihren `start_date` aus dem letzten Lauf-Zeitstempel (`{platform}_last_crawl_end`, `availability_last_run`). War der nächste Lauf bereits überfällig, startet er ~1 Minute nach Server-Start statt erst nach dem vollen Intervall. Überfällige Plattform-Jobs starten gestaffelt (60s + 15s pro Plattform) um gleichzeitige Requests zu vermeiden. Logik in `scheduler._calc_start_date(last_end_str, minutes, stagger_seconds)`.

### E-Mail-Benachrichtigung (gebündelt)
`notifier.notify_pending(settings)` läuft alle 15 Min. als `notify_job` im Scheduler. Es holt alle Listings mit `notified_at IS NULL` aus der DB (`db.get_unnotified_listings()`), sendet eine gruppierte HTML-E-Mail (nach Plattform → Suchbegriff mit Inhaltsverzeichnis, Gratis-Items grün hervorgehoben) und setzt `notified_at = NOW()` via `db.mark_listings_notified()`. Automatische Crawls rufen `notify()` nicht auf — nur der Job. Bei manuellem Crawl (`manual=True`) ruft `run_crawl()` direkt `notify()` auf, das ebenfalls `mark_listings_notified()` aufruft, damit der Job dieselben Listings nicht nochmals versendet.

### Radius 0 = kein Filter (Vinted & Shpock)
Beide Scraper lesen `vinted_radius` / `shpock_radius` via `_int()`; ist der Wert `0`, wird der Entfernungsfilter vollständig deaktiviert (kein Geocoding-Aufruf). Muster: `raw = _int(settings.get(..., "30")); self.radius_km = 30 if raw is None else raw`, Filter-Block: `if self._home and self.radius_km > 0:`.

### Vinted: Altersfilter beim Crawlen
`VintedScraper` liest `vinted_max_age_hours` aus den Settings (Default 48h). Items werden anhand des API-Felds `created_at_ts` (Unix-Timestamp) gefiltert — Items, die auf Vinted älter als der konfigurierte Wert sind, werden **vor dem Speichern** verworfen. `max_age_hours = 0` deaktiviert den Filter. Verhindert, dass wochenlang aktive Vinted-Anzeigen als „neu" gespeichert werden.

### Willhaben.at: PayLivery-Filter & Radius
`WillhabenScraper` parsed `__NEXT_DATA__` JSON aus dem HTML (Next.js SSR). Attribute werden aus einer `attributes.attribute[]`-Liste extrahiert (`_attr()`-Hilfsfunktion). Mit `willhaben_paylivery_only = "1"` (Default) wird `paylivery=true` als URL-Parameter gesetzt — nur Versand-Angebote werden zurückgegeben, und der Radius-Filter wird komplett deaktiviert (Versand nach Deutschland macht Standort irrelevant). Mit `paylivery_only = "0"` wird der Radius via Haversine auf den COORDINATES-Attribut angewendet. Pagination über `page`-Parameter (1-indexed), 30 Items pro Seite.

### markt.de: Stadtname-Slug
`MarktdeScraper` baut die Suchanfrage als `https://www.markt.de/{city_slug}/suche/{term}/`. Der Stadtname wird via `_city_slug()` normalisiert: lowercase, Umlaute ersetzt (ä→ae, ö→oe, ü→ue, ß→ss), Leerzeichen durch Bindestrich. Kein Geocoding nötig — der Radius wird direkt als URL-Parameter `?radius=N` übergeben. CSS-Selektoren können sich ändern wenn markt.de das Layout aktualisiert.

### Automatischer Cleanup dismisst Anzeigen
`clear_old_listings(days=30)` (läuft nach jedem Crawl) trägt alle zu löschenden `listing_id`s vor dem DELETE in `dismissed_listings` ein. Damit tauchen nach 30 Tagen aus der DB entfernte Anzeigen beim nächsten Crawl nicht wieder als „neu" auf — identisches Verhalten wie `clear_listings_older_than()` (manuelle Bulk-Löschung).

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

### Per-Profil-Benachrichtigungen
Jedes Profil hat eigene Felder `email`, `notify_mode`, `digest_time`, `alert_interval_minutes` (Default 15, Minimum 15 — Spamschutz) und `last_alert_sent_at`. Konfigurierbar im Settings-Tab „Profile" pro Profil.

`notify_pending()` prüft vor dem Claim: Profile mit `notify_mode=immediate/both` und gesetzter E-Mail müssen ihr `alert_interval_minutes`-Intervall seit `last_alert_sent_at` abgewartet haben. Sind Profile konfiguriert aber keines ist fällig → kein Claim, kein Versand (Listings bleiben unnotified). Nach Versand wird `last_alert_sent_at` pro Profil aktualisiert. Fallback auf globale `email_recipient`-Settings wenn kein Profil eine E-Mail hat.

Modi: `immediate` (Sofort-Alert), `digest_only` (nur Tages-Digest), `both` (Alert + Digest), `off` (stumm). Digest: `_schedule_profile_digests()` legt pro Profil mit `digest_only`/`both` und E-Mail einen eigenen CronJob an. Endpoint: `POST /profiles/<id>/notify` (JSON: `email`, `notify_mode`, `digest_time`, `alert_interval_minutes`). DB: `update_profile_notify()`, `update_last_alert_sent()`.

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
Klick auf eine Karte öffnet `#detail-modal` mit Vollbild-Details (Bild, Preis, Standort, Beschreibung, Notiz-Textarea). Daten kommen aus `listingsCache` (JS-Map, aus Jinja-`<script>`-Block befüllt). `handleCardClick(event, id)` unterscheidet zwischen Karte und Buttons. Deep-Link: `/?modal=<db_id>` öffnet das Modal direkt beim Seitenload — wird in E-Mail-Benachrichtigungen als „Im Dashboard →"-Button pro Anzeige verwendet.

### Dashboard: Plattform-Filter & Status-Bar
`loadPlatformOptions()` befüllt das Plattform-Dropdown aus `GET /api/platforms` (nur tatsächlich vorhandene Plattformen). `updatePlatformCounts()` zeigt „KA 120 · Shp 45" unter dem Gesamt-Zähler.

### KI-Assistent: Verkäufer-Anfragetext
`ai.py.generate_contact_text(listing, price_stats, settings)` generiert einen höflichen Kontakttext. Provider-Erkennung: `ai_base_url` gesetzt → Ollama; API-Key-Prefix `sk-ant-` → Anthropic; `sk-` → OpenAI; Fallback über Modellname. Bei VB-Anzeigen wird ein Preisvorschlag (85% des Durchschnittspreises aus `price_stats`, auf 5 € gerundet) in den Prompt eingebaut. `ai_prompt_hints` werden als persönliche Käufer-Hinweise an den Prompt angehängt. Fehler geben eine lesbare Warnung zurück (kein raise). Route: `POST /api/listings/<id>/contact-text`. `GET /api/ai-models` holt Modellliste vom konfigurierten Anbieter (Anthropic/OpenAI: gefiltert auf aktuelle Chat-Modelle; Ollama: lokal installierte Modelle). Im Modal: „✨ Generieren"-Button → editierbare Textarea → „📋 Kopieren". Text wird nie automatisch gesendet. Optionaler Ollama-Service: `docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d`, dann `docker exec marktcrawler-ollama ollama pull gemma2:2b`. **Nicht empfohlen für RPi4** (CPU-only, ~2–5 Min/Antwort).

### Info-Seite: Versionanzeige & Update-Check
`app/version.py` liefert die aktuelle Commit-Info (`get_current_version()`): Priorität ist `app/_version.py` (beim `docker build` via `scripts/bake_version.py` eingebrannt) → Env-Vars `GIT_COMMIT/GIT_DATE/GIT_MESSAGE` → `git`-Subprocess (Dev). `scripts/bake_version.py` liest primär das Git-Commit-Objekt direkt aus `.git/objects/<sha[:2]>/<sha[2:]>` via `zlib`-Dekomprimierung (`_commit_from_object()`): extrahiert Committer-Datum mit Timezone-Offset (korrekte lokale Datumsanzeige) + Commit-Subject. Fallback 1: `_last_commit_from_log()` durchsucht den Branch-Reflog rückwärts nach "commit:"-Einträgen. Fallback 2: neuester Reflog-Timestamp (verhindert 1970-01-01). Kein `git`-Binary nötig im Docker-Build-Kontext. `get_available_updates(hash)` ruft die GitHub-API (`/repos/{owner}/{repo}/compare/{hash}...main`) on-demand über `GET /api/check-updates` ab — kein Auto-Load, kein Cache. Commit-Hashes auf der Info-Seite sind direkte GitHub-Links. Repo-Erkennung via `GITHUB_REPO`-Env-Var (in `docker-compose.yml` vorbelegt) oder automatisch aus `git remote get-url origin`. Fällt bei Offline/private Repo stumm aus (`None`).

### Dashboard: Per-Plattform-Statusübersicht
Die ersten drei Status-Kacheln (Status / Letzter Lauf / Nächster Lauf) wurden durch eine kompakte Plattform-Tabelle (3 Spalten breit) ersetzt. Spalten: Plattform | Status (✓ Bereit / ⟳ Läuft… / deaktiviert) | Letzter Lauf (relativ mit Tooltip) | Nächster Lauf | Neue (Badge). Deaktivierte Plattformen werden gedimmt (opacity-40). `/api/status` liefert jetzt `platforms`-Array mit `{id, display, enabled, is_running, last_crawl_end, last_crawl_found, next_run}`. `_build_platform_stats(settings, next_runs)` in `routes.py` erzeugt dieses Array für Template und API. `updatePlatformTable(platforms)` in JS aktualisiert die Tabelle live beim Polling.

## Arbeitsweise & Dokumentationsregeln

- **Nach jeder Implementierung committen**: Kein offenes Work-in-Progress lassen. Am Ende jeder Feature/Fix-Session prüfen ob `README.md`, `docs/features.md`, `TASKS.md` und `CLAUDE.md` veraltet sind — dann anpassen und committen.
- **README vs. features.md**: `README.md` enthält nur eine knappe Auswahl der stärksten Features (~8–10 Bullets). `docs/features.md` enthält **alle** Features vollständig und ausführlich. Jedes Feature das in der README erwähnt wird, muss auch einen eigenen Abschnitt in der `features.md` haben — eine reine Tabellenzeile reicht nicht.

## Wichtige Konventionen

- **Scraper-Interface**: Alle Scraper erben von `BaseScraper(ABC)` aus `scrapers/base.py`. `search()` ist `@abstractmethod` – falsche Implementierungen werfen `TypeError` statt stille Fehler. Jeder Scraper hat `__init__(self, settings: dict)` mit `super().__init__(settings)` und `search(self, term: str, max_results: int) -> List[Listing]`. `settings` ist das komplette Dict aus `db.get_settings()`.
- **Neuen Scraper hinzufügen**: Neue Klasse in `app/scrapers/` (erbt von `BaseScraper`), in `crawler.py` in die Scraper-Liste eintragen, in `routes.py` und `settings.html` entsprechende Felder ergänzen.
- **Kein ORM**: Alle DB-Zugriffe direkt mit `sqlite3` in `database.py`. Neue Abfragen dort als Funktion anlegen.
- **Kein JS-Build**: Tailwind via CDN. Kein npm. JS direkt in den Templates als `<script>`-Blöcke.
- **Thread-Safety**: `crawler.py` und `checker.py` nutzen je ein eigenes `threading.Lock` + `_running`-Flag. Nie direkt `run_crawl()` aufrufen – immer `run_crawl_async()`.
- **Settings-Checkboxen**: In HTML-Forms senden Checkboxen keinen Wert wenn nicht angehakt. `routes.py → save_settings()` behandelt das explizit mit `"1" if request.form.get(key) else "0"`.
- **Datenbankpfad**: `DATA_DIR`-Umgebungsvariable (Default `/data`). Lokal via `.env`: `DATA_DIR=./data`.
- **E-Mail-Credentials**: `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECIPIENT`, `EMAIL_SMTP_SERVER`, `EMAIL_SMTP_PORT` als Env-Vars setzen – haben Vorrang vor DB-Settings. Nützlich für Docker/CI ohne DB-Zugriff.
- **`last_crawl_found`**: Wird pro Plattform als `{platform}_last_crawl_found` in Settings gespeichert. `routes.py` summiert alle Plattformen für Dashboard/API. Kein globaler `last_crawl_found`-Key (wurde als Race-Condition-Fix entfernt).

## Lokale Entwicklung

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium       # einmalig nach Installation (für Tests + Facebook)

# .env bereits vorhanden mit DATA_DIR=./data
python run.py                     # startet auf http://localhost:5000
```

## Tests

```bash
pytest tests/                     # alle Tests (579 Unit/Integration + 19 Playwright UI)
pytest tests/test_ui.py           # nur UI-Tests (Playwright, ~30s)
pytest tests/test_ui.py --headed  # UI-Tests mit sichtbarem Browser
pytest tests/ --ignore=tests/test_ui.py  # nur Unit/Integration-Tests
```

**Teststruktur:**
- `tests/test_ui.py` — Playwright End-to-End-Tests für kritische Frontend-Features (Prio 1–3): Dashboard, Pagination/„Mehr laden"-Button, Crawl-Feedback, Dismiss, Suchbegriffe, Filter, API-Schema, Favoriten, Settings-Tabs, Profil-Flow
- `tests/test_routes.py` — Flask-Routen und REST-API (pytest)
- `tests/test_database.py` — DB-Operationen (pytest)
- `tests/conftest.py` — Shared Fixtures: `temp_db` (leere Test-DB), `live_server` (Flask-Server mit 35 Test-Listings für Playwright)

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
| GET | `/api/status` | Crawler-Status als JSON (inkl. `platforms`-Array mit per-Plattform-Status) |
| GET | `/api/listings` | Anzeigen als JSON (`?term=`, `?platform=`, `?limit=30`, `?offset=0`, `?favorites=1`, `?free=1`, `?max_age=`, `?max_distance=`, `?sort=date_desc`, `?exclude=`) |
| GET | `/api/stats` | Preisstatistik pro Suchbegriff (JSON) |
| POST | `/listings/<id>/dismiss` | Anzeige dauerhaft ausblenden (JSON) |
| POST | `/listings/<id>/note` | Notiz setzen/löschen (JSON: `{"note": "..."}`) |
| POST | `/terms/<id>/max-price` | Preis-Schwelle für Term setzen (JSON: `{"max_price": N}`) |
| GET | `/api/platforms` | Distinct Plattformen der gespeicherten Anzeigen (JSON Array) |
| POST | `/api/test-scraper` | Scraper-Verbindung testen (JSON: `{"platform": "kleinanzeigen"}`) |
| POST | `/api/clear-listings-by-age` | Anzeigen löschen + dismissen die älter als `hours` sind (JSON body: `{"hours": N}`) |
| GET | `/api/check-updates` | Vergleicht aktuellen Commit-Hash mit `main` auf GitHub; liefert `{status, updates, count, repo_url}` |
| GET | `/profiles/select` | Profil-Auswahl-Seite (nur wenn Profile existieren) |
| POST | `/profiles/select/<id>` | Profil aktivieren, `last_seen_at` in DB aktualisieren, Session setzen |
| POST | `/profiles/logout` | Session leeren, zurück zur Profilauswahl |
| POST | `/profiles` | Neues Profil anlegen (form: `name`, `emoji`) |
| POST | `/profiles/<id>/update` | Profil umbenennen/Emoji ändern (JSON: `{"name": "...", "emoji": "..."}`) |
| POST | `/profiles/<id>/delete` | Profil löschen (JSON response) |
| POST | `/api/cleanup-mismatched` | Nicht passende Anzeigen bereinigen (JSON: `{"deleted": N}`) |

## Bekannte Einschränkungen

- Kleinanzeigen.de ändert gelegentlich seine HTML-Selektoren → CSS-Selektoren in `kleinanzeigen.py._parse()` ggf. anpassen.
- Facebook Marketplace benötigt interaktiven einmaligen Login und Playwright (`playwright install chromium`).
- Shpock GraphQL-Schema kann sich ändern → Query in `shpock.py` ggf. anpassen. Shpock ignoriert den Location-Filter ohne Session – Radius-Filterung erfolgt client-seitig via Geocoding.
- Vinted benötigt beim Start einen anonymen Session-Cookie (wird automatisch via `_authenticate()` geholt). Bei 401 erfolgt ein automatischer Retry.
- Willhaben.at: `__NEXT_DATA__`-Struktur kann sich bei Next.js-Updates ändern → JSON-Pfad in `_extract_adverts()` ggf. anpassen. Willhaben erlaubt nur Suche in Österreich; PayLivery-Filter empfohlen für Versand nach Deutschland.
- markt.de: CSS-Selektoren (`.clsy-c-result-list-item*`) können sich bei Layout-Updates ändern. Stadt-Slug muss existieren; bei unbekannten Städten gibt markt.de ggf. eine 404-Seite zurück.
- Nominatim-Geocoding funktioniert nur wenn der Standorttext in der Anzeige eindeutig genug ist. Bei unklaren Ortsangaben wird kein Treffer zurückgegeben.
- Gunicorn läuft mit `--workers 1`, da SQLite kein Multi-Process-Writing ohne WAL gut verträgt (WAL ist aktiviert).
