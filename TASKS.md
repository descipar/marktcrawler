# 📋 Baby-Crawler – Aufgaben & Roadmap

---

## 🔜 Offene Aufgaben

Zum Umsetzen einfach den Kategorienamen nennen (z.B. „mach Accessibility") oder einzelne Tasks per Nummer (z.B. „mach 8 und 11").

---

### Accessibility

- [ ] **8** – `aria-label` auf Icon-Buttons (✕, ★), `label[for]`-Verknüpfung auf allen Formularfeldern, `aria-live`-Region für Listings, Skip-Nav-Link
- [ ] **9** – Kontrast-Fixes: `slate-400` → `slate-500/600` an Hint-Texten und Metadaten
- [ ] **19** – `alert()`/`confirm()` durch barrierefreie Inline-Meldungen und eigenes Confirm-Modal ersetzen

---

### Features – KI-Integration

- [ ] **26** – KI-Anfragetext-Generator: auf Wunsch pro Anzeige einen Verkäufer-Text per Knopfdruck generieren; bei VB-Anzeigen automatisch einen sinnvollen Preisvorschlag einbauen (basiert auf `price_stats` der eigenen Daten); API-Key konfigurierbar (Claude, OpenAI, oder andere); Text wird immer in einer editierbaren Textarea angezeigt, kein direktes Absenden; Modell + API-Key in Einstellungen hinterlegbar

---

### Features – Benachrichtigungen

- [ ] **12** – Telegram-Bot als Alternative zu SMTP (Bot-Token + Chat-ID, Alert + Digest)
- [ ] **20** – Browser Push Notifications (Web Push API, kein E-Mail-Setup nötig)

---

### Features – Mehrbenutzer

- [ ] **10** – Profil-System à la Netflix: „Neu"-Badge pro Person, `last_seen_at` pro Profil in DB; jede Person sieht welche Anzeigen seit ihrem letzten Besuch neu sind

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

---

*Letzte Aktualisierung: 2026-04-26 (Phase 15 abgeschlossen)*
