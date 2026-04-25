# 📋 Baby-Crawler – Aufgaben & Roadmap

Übersicht aller erledigten und geplanten Aufgaben.

---

## ✅ Erledigt

### Phase 1 – Grundgerüst
- [x] Projektstruktur anlegen (`app/`, `scrapers/`, `templates/`)
- [x] Kleinanzeigen.de Scraper (`requests` + `BeautifulSoup`)
- [x] Shpock Scraper (GraphQL-API)
- [x] Facebook Marketplace Scraper (Playwright, optional)
- [x] `Listing`-Datenklasse als gemeinsame Scraper-Schnittstelle
- [x] SQLite-Datenbankschicht ohne ORM (`database.py`)
- [x] E-Mail-Benachrichtigung per SMTP (`notifier.py`)
- [x] APScheduler-Integration für automatischen Crawl (`scheduler.py`)
- [x] Flask App Factory + Blueprint-Routen (`routes.py`)
- [x] Admin-UI: Dashboard mit Suchbegriff-Verwaltung und Anzeigen-Grid (`index.html`)
- [x] Einstellungsseite für alle Plattformen und E-Mail (`settings.html`)
- [x] Docker-Setup (`Dockerfile`, `docker-compose.yml`)
- [x] Mehrere E-Mail-Empfänger (kommagetrennt)
- [x] Duplikat-Erkennung über `listing_id`

### Phase 2 – Lokale Entwicklung
- [x] `DATA_DIR`-Umgebungsvariable für flexiblen DB-Pfad
- [x] `.env`-Datei für lokale Entwicklung (`DATA_DIR=./data`)
- [x] `python-dotenv` in `run.py` eingebunden
- [x] Mehrwort-Suche auf Kleinanzeigen.de gefixt (`q-`-Prefix-URL)

### Phase 3 – Erweiterte Features
- [x] **🎁 Gratis-Erkennung** – Regex auf Preis + Keywords in Titel/Beschreibung (`_is_free()`)
- [x] **🚫 Blacklist** – Anzeigen mit bestimmten Wörtern automatisch überspringen
- [x] **⭐ Favoriten** – Anzeigen markieren, AJAX-Toggle, nie automatisch gelöscht
- [x] **📊 Preisstatistik** – Avg / Min / Max / Gratis-Zähler pro Suchbegriff (Dashboard + API)
- [x] **📍 Entfernungsberechnung** – Nominatim-Geocoding + Haversine-Formel (`geo.py`)
- [x] **🕐 Altersfilter** – Anzeigen nach Stunden filtern (Dashboard + API)
- [x] **📋 Tages-Digest** – tägliche Zusammenfassung per E-Mail via CronTrigger
- [x] Geocoding-Cache in DB (`geocache`-Tabelle, Rate-Limit 1 req/s)
- [x] DB-Migration für bestehende Installationen (neue Spalten via `PRAGMA table_info`)
- [x] Einstellungsseite um neue Felder ergänzt (Blacklist, Digest, Heimstandort, Max-Alter)
- [x] Blacklist-Bug gefixt: Textarea sendet Zeilenumbrüche, kein Komma

### Phase 4 – Qualität & Dokumentation
- [x] **115 Unit-Tests** mit pytest
  - `test_crawler.py` – `_is_free()` und `_is_blacklisted()` (30 Tests)
  - `test_database.py` – CRUD, Migration, Favoriten, Geocache (25 Tests)
  - `test_geo.py` – Haversine, Geocoding-Cache, `distance_to_home()` (13 Tests)
  - `test_notifier.py` – HTML/Text-Builder, Badges, E-Mail-Struktur (25 Tests)
  - `test_scrapers.py` – VintedScraper, EbayScraper (22 Tests)
- [x] `CLAUDE.md` mit Architektur, DB-Schema, API-Dokumentation und Konventionen
- [x] `README.md` mit Deployment-Optionen (RPi4, Proxmox, lokal), Features, Tests

### Phase 5 – Bugfixes & Code-Qualität
- [x] **SECRET_KEY** aus Umgebungsvariable statt hardcoded (`app/__init__.py`)
- [x] **Vinted & eBay** in `allowed_keys`, `DEFAULT_SETTINGS` und `settings.html` ergänzt (waren de facto deaktiviert)
- [x] **`Listing.distance_km`** Typhinweis korrigiert (`float` → `Optional[float]`)
- [x] **Code-Duplikat** – `_int`, `_float`, `price_within_limit` in `base.py` zentralisiert, aus allen Scrapers entfernt
- [x] **Shpock-Preis-Parsing** – fragilen `>500`-Schwellenwert durch korrektes `/100` für alle Cent-Preise ersetzt
- [x] **ValueError** in `/api/listings` bei ungültigem `?limit=` oder `?max_age=` (HTTP 400 statt 500)
- [x] **Thread-Safety Geocoding** – `_nominatim_lock` in `geo.py` schützt Rate-Limit und API-Call
- [x] **`geocache`-Spalte `cached_at`** im Schema und Migration ergänzt (war in CLAUDE.md dokumentiert, fehlte in DB)
- [x] **`is_running()` und `finally`** in `crawler.py` nutzen jetzt den `_lock`
- [x] **Notifier-Duplikat** – `_html_from_objects` / `_text_from_objects` entfernt; `_send()` nutzt `dataclasses.asdict()` + gemeinsame Dict-Builder
- [x] **SQLite-Timeout erhöht** – `timeout=30` in `get_db()` behebt `database is locked`-Fehler bei gleichzeitigem Crawler-Write und Flask-API-Polling

### Phase 6 – Shpock-Reaktivierung & Bugfixes
- [x] **Shpock-Scraper komplett überarbeitet** – neue GraphQL-Query-Struktur (`ItemSearch` mit `serializedFilters`, Key `"q"` statt `"keyword"`), Preise direkt in Euro (kein `/100` mehr), Bild-URLs via `secondhandapp.at`
- [x] **Shpock Entfernungsfilter** – API liefert `distance: null` ohne Session; client-seitiger Geo-Filter via Nominatim-Geocoding + Haversine; API-Request auf `3×max_results` erhöht um mehr Kandidaten zu filtern; Log-Warnung wenn 0 Treffer im Radius
- [x] **`_is_free()`-Bug** – Preis hat jetzt Vorrang vor Text-Keywords: ein Listing mit echtem Preis > 0 wird nie als gratis markiert, auch wenn Beschreibung Wörter wie „gratis Zubehör" enthält
- [x] **Shpock-Warnung in `settings.html` entfernt** – veralteter Hinweis auf defekte API
- [x] **Vinted 401 gefixt** – Vinted setzt `access_token_web`-JWT-Cookie erst beim Startseiten-Besuch; `_authenticate()` holt Cookie einmalig im `__init__`, bei erneutem 401 automatischer Retry; Preis-Parsing auf neues API-Format `{"amount": "...", "currency_code": "..."}` umgestellt
- [x] **Tests nachgezogen** – 14 neue Tests für alle Änderungen dieser Phase: `_is_free`-Grenzfälle (echter Preis vs. Text, VB-Preis), Shpock `_parse`/Radius/Preis/Auth-Filter, Vinted Auth-Init und 401-Retry; bestehende Tests an neue Formate angepasst (130 Tests gesamt)

---

## 🔜 Geplant

### Benachrichtigungen
- [ ] **Telegram-Bot** – Sofort-Benachrichtigung via Bot-API als Alternative zu E-Mail
- [ ] Push-Benachrichtigungen (ntfy.sh oder Gotify, self-hosted)

### Scraper
- [x] **eBay** – Scraper für eBay-Auktionen und Sofortkauf
- [x] **Vinted** – Scraper für Kinderkleidung auf Vinted
- [ ] Preishistorie pro Anzeige speichern (Preisentwicklung verfolgen)

### UI & Filterung
- [ ] Anzeigen als „gesehen" markieren (Badge ausblenden ohne zu favorisieren)
- [ ] Direktlink zu gefilterter Ansicht per URL teilen
- [ ] Dunkelmodus

### Infrastruktur
- [ ] Automatisches Backup der SQLite-DB (z.B. tägliches `cp` per Cron)
- [ ] Health-Check-Endpoint (`/health`) für Docker / Uptime-Monitoring

---

*Letzte Aktualisierung: 2026-04-25 (Vinted-Auth-Fix + Preis-Parsing)*
