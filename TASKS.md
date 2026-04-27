# 📋 Baby-Crawler – Aufgaben & Roadmap

---

## 🔜 Offene Aufgaben

Zum Umsetzen einfach den Kategorienamen nennen (z.B. „mach Accessibility") oder einzelne Tasks per Nummer (z.B. „mach 8 und 11").

---

~~### Accessibility~~ ✅ (Phase 18)

---

~~### Code-Qualität & Robustheit~~ ✅ (Phase 16)

---

### Features – KI-Integration

- [ ] **KI** – KI-Anfragetext-Generator: auf Wunsch pro Anzeige einen Verkäufer-Text per Knopfdruck generieren; bei VB-Anzeigen automatisch einen sinnvollen Preisvorschlag einbauen (basiert auf `price_stats` der eigenen Daten); API-Key konfigurierbar (Claude, OpenAI, oder andere); Text wird immer in einer editierbaren Textarea angezeigt, kein direktes Absenden; Modell + API-Key in Einstellungen hinterlegbar

---

### Features – Benachrichtigungen

- [ ] **12** – Telegram-Bot als Alternative zu SMTP (Bot-Token + Chat-ID, Alert + Digest)
- [ ] **20** – Browser Push Notifications (Web Push API, kein E-Mail-Setup nötig)

---

~~### Features – Mehrbenutzer~~ ✅ (Phase 17)

---

### Features – Daten & Export

- [ ] **13** – CSV/JSON-Export der aktuell gefilterten Anzeigen (clientseitiger Download, kein Server-Endpoint nötig)
- [ ] **23** – Settings-Backup: Import/Export als JSON-Datei

---

### Features – Komfort & Bedienung

- [ ] **11** – Tastaturkürzel: j/k navigieren, f favorisieren, d dismisssen, / Suche fokussieren, ? Hilfe-Overlay
- [ ] **21** – Dark Mode (`prefers-color-scheme` + manueller Toggle, Zustand in `localStorage`)
- [ ] **22** – PWA-Manifest: App auf Smartphone installierbar (Homescreen-Icon, Offline-Splash)

---

## ✅ Erledigt

### Phase 1 – Grundgerüst
- [x] Projektstruktur, Kleinanzeigen-Scraper, Shpock-Scraper (GraphQL), Facebook-Scraper (Playwright)
- [x] `Listing`-Datenklasse, SQLite-Schicht ohne ORM, E-Mail-Benachrichtigung, APScheduler
- [x] Flask App Factory + Blueprint, Dashboard, Einstellungsseite, Docker-Setup
- [x] Mehrere E-Mail-Empfänger, Duplikat-Erkennung über `listing_id`

### Phase 2 – Lokale Entwicklung
- [x] `DATA_DIR`-Umgebungsvariable, `.env`-Datei, `python-dotenv`, Mehrwort-Suche gefixt

### Phase 3 – Erweiterte Features
- [x] 🎁 Gratis-Erkennung, 🚫 Blacklist, ⭐ Favoriten, 📊 Preisstatistik
- [x] 📍 Entfernungsberechnung (Nominatim + Haversine), 🕐 Altersfilter, 📋 Tages-Digest
- [x] Geocoding-Cache, DB-Migration, Blacklist-Bug (Textarea Zeilenumbrüche)

### Phase 4 – Qualität & Dokumentation
- [x] 115 Unit-Tests, CLAUDE.md, README.md

### Phase 5 – Bugfixes & Code-Qualität
- [x] SECRET_KEY aus Env, Vinted/eBay in Settings ergänzt, Helfer in `base.py` zentralisiert
- [x] Shpock-Preis-Parsing, ValueError HTTP 400, Thread-Safety Geocoding, SQLite-Timeout 30s

### Phase 6 – Shpock-Reaktivierung & Bugfixes
- [x] Shpock GraphQL komplett überarbeitet, Entfernungsfilter client-seitig
- [x] `_is_free()`-Bug (Preis hat Vorrang vor Text), Vinted 401 + neues API-Format
- [x] 14 neue Tests (130 gesamt)

### Phase 7 – Standort/Radius + Konfigurierbarkeit
- [x] Vinted + eBay Standort/Radius, Crawl-Intervall-Default 15 Min.
- [x] Scheduler-Bug `next_crawl`, E-Mail-Betreff konfigurierbar

### Phase 8 – Code-Qualität & Testabdeckung
- [x] DB-Verbindungs-Leaks gefixt (`_db()` Context-Manager), `geo.py` Robustheit
- [x] Input-Validierung in `routes.py`, Silent-Exception in Crawler gefixt
- [x] 30 neue Tests `test_routes.py`, 13 neue Tests `test_crawl_run.py` (180 gesamt)

### Phase 9 – Pagination, Mobile-UI & E-Mail manuell
- [x] Pagination (`offset`, „Mehr laden"-Button), Mobile-UI (kollabierbare Sidebar, horizontale Filter-Leiste)
- [x] E-Mail bei manuellem Crawl (`force=True` überspringt Rate-Limit)

### Phase 10 – Sortierfunktion
- [x] Sortierung nach Datum, Preis, Entfernung; Preis-CAST via `GLOB`; Favoriten immer oben
- [x] `/api/listings?sort=` mit Whitelist, Dashboard-Dropdown (188 Tests)

### Phase 11 – Verfügbarkeits-Check
- [x] `checker.py` mit HEAD-Requests (404/410 → löschen inkl. Favoriten)
- [x] Scheduler-Job, Settings, `POST /api/availability-check` (200 Tests)

### Phase 12 – Radius-0, Suchbegriff-Filter & Exclude-Filter
- [x] Radius=0 deaktiviert Entfernungsfilter (Vinted & Shpock)
- [x] Suchbegriff-Filter (Klick auf Term), Exclude-Filter mit Debounce (208 Tests)

### Phase 13 – Dismiss & Term-Delete
- [x] `dismissed_listings`-Tabelle, ✕-Button auf Karten, Term-Löschen löscht Anzeigen
- [x] `_listing_card.html` auf Stand gebracht (218 Tests)

### Phase 14 – Suchbegriff-Mehrfachfilter
- [x] Mehrere Terme gleichzeitig filtern (Toggle, `?term=a&term=b`), visuelle Hervorhebung (224 Tests)

### Phase 15 – Dashboard-UX, Settings-Tabs & neue Features
- [x] **1** Settings: 3-Tab-Layout (Plattformen / Benachrichtigungen / Crawler & Daten)
- [x] **2** Settings: deaktivierte Plattformen optisch dimmen
- [x] **3** Settings: sticky Save-Button + Unsaved-Changes-Warnung
- [x] **15** Settings: Inline-Validierung + `showFieldError()` wechselt automatisch Tab
- [x] **16** Settings: „Verbindung testen"-Button pro Plattform
- [x] **4** Dashboard: ausklappbares Filter-Panel mit Aktiv-Badge
- [x] **5** Dashboard: relative Zeitangaben („vor 2h") auf Karten
- [x] **6** Dashboard: Listing-Detailansicht per Modal
- [x] **7** Dashboard: Log-Terminal standardmäßig eingeklappt
- [x] **17** Dashboard: Plattform-Filter aus `/api/platforms` (nur vorhandene Plattformen)
- [x] **18** Dashboard: Status-Bar mit Anzeigen pro Plattform + relative Laufzeit
- [x] **14** Feature: Duplikat-Erkennung plattformübergreifend (Amber-Badge)
- [x] **24** Feature: Notizfeld pro Anzeige (💬-Badge, Modal-Textarea)
- [x] **25** Feature: Preis-Schwelle pro Suchbegriff (Inline-Edit in Sidebar)
- [x] Checker: `_running`-Guard, `min_age_minutes=60` für frische Anzeigen
- [x] API: `/terms/<id>/max-price`, `/listings/<id>/note`, `/api/platforms`, `/api/test-scraper`, `/api/clear-listings-by-age`, `platform_counts` in `/api/status`
- [x] DB: `notes`, `potential_duplicate` (listings), `max_price` (search_terms), Migration sicher
- [x] 41 neue Tests (259 gesamt)

### Phase 16 – Code-Qualität & Robustheit
- [x] **26** Badge-Klassen zentralisiert: `badge-vt`/`badge-eb` in `base.html`, `getPlatformBadgeClass()` in JS, Vinted/eBay in `_PLATFORM_COLORS`
- [x] **27** Magic Numbers als Konstanten: `LOG_POLL_INTERVAL_MS`, `EXCLUDE_DEBOUNCE_MS`, `TOAST_DURATION_MS` (index.html + settings.html)
- [x] **28** `getPlatformBadgeClass()` extrahiert, `cardHtml()` + `openModal()` nutzen Helper
- [x] **29** Jinja2-Macro `platform_section` in `settings.html`: 5 Plattform-Blöcke → 1 Macro
- [x] **30** `geo.py`: leere Strings statt Null-Check für Heimkoordinaten, 0.0/0.0 ist jetzt gültig
- [x] **31** JS `fetch()`-Fehler: `showToast()` bei Netzwerkfehler in `startCrawl`, `dismissListing`, `toggleFav`
- [x] **32** `notifier.py`: `distance_km is not None` statt falsy-Check (0.0 km korrekt ausgegeben)
- [x] **33** `checker.py`: erwartete Laufzeit beim Start loggen, Delete-Logs auf `debug()` gesenkt
- [x] 1 neuer Test, 1 Test korrigiert (260 gesamt)

### Phase 17 – Mehrbenutzer-Profile
- [x] **10** Profil-System (Netflix-Stil): Profil-Auswahl beim Start, `profiles`-Tabelle in DB
- [x] Suchbegriffe global geteilt; `last_seen_at` pro Profil für „Neu"-Badge
- [x] ✨ Neu-Badge auf Karten und im Modal für Anzeigen seit letztem Besuch
- [x] Profil-Verwaltung in Settings (neuer Tab „Profile"): anlegen, bearbeiten, löschen
- [x] Aktives Profil + Wechsel-Button in der Navbar
- [x] Neue Route `/profiles/select`, `/profiles/select/<id>`, `/profiles/logout`
- [x] 17 neue Tests (277 gesamt)

---

### Phase 18 – Accessibility
- [x] **8** `aria-label` auf ✕/★-Buttons (Karte + cardHtml), Skip-Nav-Link, `aria-live` auf Listings-Grid
- [x] **9** Kontrast: `slate-400` → `slate-500` an Metadaten und Hint-Texten in allen Templates
- [x] **19** `alert()`/`confirm()` durch barrierefreies Confirm-Modal (base.html) und `showToast()` ersetzt

### Phase 19 – Unabhängige Plattform-Scheduler + gebündelte Benachrichtigung
- [x] Pro Plattform ein eigener APScheduler-Job mit konfiguriertem Intervall (z.B. Kleinanzeigen 15 Min., eBay 60 Min.)
- [x] Manueller Crawl mit Plattform-Auswahl (Dropdown: „Alle aktiven" oder einzelne Plattform)
- [x] `DEFAULT_INTERVALS` pro Plattform, `{platform}_interval`-Einstellung pro Plattform in DB/Settings
- [x] `notified_at TEXT`-Spalte in `listings`-Tabelle (Migration), `get_unnotified_listings()`, `mark_listings_notified()`
- [x] `notify_pending()`: gebündelte E-Mail alle 15 Min. für alle unbenachrichtigten Anzeigen
- [x] HTML-E-Mail gruppiert nach Plattform → Suchbegriff mit Inhaltsverzeichnis; Gratis-Items grün hervorgehoben
- [x] Automatische Crawls benachrichtigen nicht direkt; `notify()` nur noch bei `manual=True`
- [x] 13 neue Tests (300 gesamt)

### Phase 20 – Architektur-Fixes & Test-Absicherung
- [x] SQLite-Performance-Indexes auf `platform`, `search_term`, `found_at`, `is_favorite`, `notified_at` via `_ensure_indexes()` (nach Migrations ausgeführt)
- [x] Versioniertes Migrations-Framework: `_migrations`-Tracking-Tabelle, `_run_pending_migrations()`, jede Migration läuft genau einmal
- [x] E-Mail-Credentials via Env-Vars (`EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECIPIENT`, `EMAIL_SMTP_SERVER`, `EMAIL_SMTP_PORT`) mit DB-Fallback
- [x] Race Condition behoben: globaler `last_crawl_found`-Key aus Crawler entfernt; `routes.py` summiert `{platform}_last_crawl_found` aller Plattformen
- [x] `BaseScraper(ABC)` mit `@abstractmethod search()` – alle 5 Scraper erben davon, Interface ist nun enforced
- [x] HTML-E-Mail-Builder vereinheitlicht: `_html_email()` ersetzt zwei separate Builder; Aliases für Rückwärtskompatibilität
- [x] 23 neue Tests (323 gesamt): Migrations-Framework, Indexes, Env-Var-Priorität, Race-Condition-Fix, BaseScraper-Vererbung, `_html_email` direkt

### Phase 21a – Migration-Fix: notified_at-Backfill verhindert Massen-E-Mail
- [x] `v4_backfill_notified_at`-Migration: setzt `notified_at = NOW()` für alle bestehenden NULL-Einträge beim Upgrade
- [x] `mark_listings_notified()` in Chunks à 500 IDs (SQLite-Variablen-Limit-Schutz)
- [x] Test: Backfill-Migration markiert alle bestehenden Listings, kein NULL übrig
- [x] CLAUDE.md: v4-Migration dokumentiert

### Phase 21 – Per-Plattform-Statusübersicht im Dashboard
- [x] `/api/status` liefert `platforms`-Array: pro Plattform `id`, `display`, `enabled`, `is_running`, `last_crawl_end`, `last_crawl_found`, `next_run`
- [x] Hilfsfunktion `_build_platform_stats()` in `routes.py` (für Template und API gemeinsam genutzt)
- [x] Dashboard: Status-/Letzter-Lauf-/Nächster-Lauf-Kacheln ersetzt durch kompakte Plattform-Tabelle (3-Spalten-breit)
- [x] Tabellenspalten: Plattform | Status (✓/⟳/deaktiviert) | Letzter Lauf (relativ) | Nächster Lauf | Neu (Badge)
- [x] Live-Update via `updatePlatformTable()` im `pollStatus`-Polling und beim Seitenstart
- [x] Deaktivierte Plattformen werden gedimmt (opacity-40) angezeigt

---

*Letzte Aktualisierung: 2026-04-27 (Phase 21 abgeschlossen)*
