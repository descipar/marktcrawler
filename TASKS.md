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
- [x] **93 Unit-Tests** mit pytest
  - `test_crawler.py` – `_is_free()` und `_is_blacklisted()` (30 Tests)
  - `test_database.py` – CRUD, Migration, Favoriten, Geocache (25 Tests)
  - `test_geo.py` – Haversine, Geocoding-Cache, `distance_to_home()` (13 Tests)
  - `test_notifier.py` – HTML/Text-Builder, Badges, E-Mail-Struktur (25 Tests)
- [x] `CLAUDE.md` mit Architektur, DB-Schema, API-Dokumentation und Konventionen
- [x] `README.md` mit Deployment-Optionen (RPi4, Proxmox, lokal), Features, Tests

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

*Letzte Aktualisierung: 2026-04-24*
