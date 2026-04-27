# Marktcrawler – Feature-Dokumentation

Vollständige Beschreibung aller Features, der Admin-UI und der API-Endpunkte.

## Inhaltsverzeichnis

- [Suche & Filterung](#suche--filterung)
- [Anzeigen-Verwaltung](#anzeigen-verwaltung)
- [Benachrichtigungen & Automatisierung](#benachrichtigungen--automatisierung)
- [KI-Assistent](#ki-assistent)
- [Admin-UI: Dashboard](#admin-ui-dashboard)
- [Admin-UI: Einstellungen](#admin-ui-einstellungen)
- [API-Endpunkte](#api-endpunkte)
- [Architektur](#architektur)

---

## Suche & Filterung

### Suchbegriffe
Suchbegriffe werden in der Sidebar verwaltet: hinzufügen, aktivieren/deaktivieren, löschen. Beim Löschen eines Suchbegriffs werden auch alle zugehörigen Anzeigen entfernt. Pro Suchbegriff kann eine optionale Preisobergrenze gesetzt werden (Stift-Icon → Eingabefeld → ENTER), die den globalen Plattform-Maximalpreis überschreibt.

### Plattformen
Gleichzeitig durchsuchbar: **Kleinanzeigen.de**, **Shpock**, **Vinted**, **eBay**, **Facebook Marketplace** (optional). Jede Plattform hat ein eigenes konfigurierbares Crawl-Intervall (Standard: Kleinanzeigen 15 Min., Shpock/Vinted 30 Min., eBay/Facebook 60 Min.).

### Blacklist
Stichworte wie „defekt" oder „bastler" können zeilenweise in die Blacklist eingetragen werden. Groß-/Kleinschreibung wird ignoriert. Blacklistete Anzeigen werden still übersprungen — kein Speichern, keine Benachrichtigung.

### Radius-Filter
Radius pro Plattform konfigurierbar in km. Geocoding über OpenStreetMap/Nominatim, Distanzberechnung via Haversine-Formel. Ergebnisse werden gecacht (kein doppelter API-Aufruf). **Radius 0 = kein Filter** (kein Geocoding-Aufruf).

### Dashboard-Filter
- **Suchbegriff-Filter** — Klick auf einen Suchbegriff in der Sidebar filtert die Liste; mehrere Begriffe gleichzeitig wählbar (Toggle). Aktive Begriffe werden blau hervorgehoben.
- **Exclude-Filter** — Freitexteingabe mit 400 ms Debounce; blendet Anzeigen aus deren Titel oder Beschreibung den Begriff enthält. ×-Button zum Zurücksetzen.
- **Altersfilter** — nur Anzeigen der letzten 3h / 6h / 24h / 48h anzeigen (Dropdown).
- **Plattform-Filter** — nur eine Plattform anzeigen (Dropdown, nur tatsächlich vorhandene Plattformen).
- **Entfernungsfilter** — max. Entfernung in km.
- **Gratis-Filter** — nur kostenlose Anzeigen.
- **Favoriten-Filter** — nur markierte Anzeigen.

Der Filter-Bereich ist ein-/ausklappbar. Anzahl aktiver Filter wird als Badge am Toggle-Button angezeigt. Zustand wird in `localStorage` gespeichert.

### Sortierung
Sortierbar nach: Datum (neu → alt, Standard), Datum (alt → neu), Preis (auf-/absteigend), Entfernung. Favoriten stehen unabhängig von der Sortierung immer oben.

---

## Anzeigen-Verwaltung

### Detail-Modal
Klick auf eine Karte öffnet das Detail-Modal mit Vollbild-Bild, Preis, Standort, vollständiger Beschreibung, Notiz-Textarea und KI-Anfragetext-Generator. „↗ öffnen" auf der Karte führt direkt zur Anzeige auf der Plattform.

### Favoriten
⭐ auf der Karte oder im Modal toggelt den Favoriten-Status (AJAX, kein Seitenneustart). Favoriten werden beim automatischen Aufräumen (clear_old_listings) **nie** gelöscht. Dashboard-Filter: `?favorites=1`.

### Notizen
Pro Anzeige eine private Notiz hinterlegen — editierbar im Detail-Modal, Auto-Save. Leer lassen zum Löschen. Karten mit Notiz zeigen ein 💬-Badge.

### Ausblenden (Dismiss)
✕-Button auf der Karte blendet eine Anzeige dauerhaft aus. Sie wird sofort gelöscht und beim nächsten Crawl nicht wieder angezeigt — auch wenn sie neu gefunden wird.

### Gratis-Erkennung
Anzeigen mit Preis 0 € / „zu verschenken" / „gratis" werden automatisch erkannt und mit 🎁-Badge gekennzeichnet. Ein echter Preis > 0 hat immer Vorrang, damit „gratis Zubehör dabei" kein False-Positive auslöst.

### Duplikat-Erkennung
Gleiche `listing_id` wird nie doppelt gespeichert. Plattformübergreifend: gleicher Titelanfang auf einer anderen Plattform (letzte 30 Tage) wird als Amber-Badge „📋 auch auf Shpock" markiert.

### Entfernungsanzeige
Luftlinie vom eigenen Heimstandort zu jeder Anzeige, berechnet via Nominatim + Haversine. Heimstandort in **Einstellungen → Crawler & Daten** als Stadtname eingeben.

### Preisstatistik
Aufklappbare Tabelle im Dashboard zeigt Durchschnitt, Min, Max und Gratis-Zähler pro Suchbegriff (`GET /api/stats`).

### Relative Zeitangaben
Timestamps werden als „vor 2h" / „vor 30 Min." angezeigt (Tooltip mit absolutem Datum).

### Pagination
30 Anzeigen pro Seite, „Mehr laden"-Button lädt weitere per AJAX.

### Verfügbarkeits-Check
Prüft periodisch per HEAD-Request ob Anzeigen noch online sind. HTTP 404/410 → automatisch löschen (inkl. Favoriten). Konfigurierbar: Aktiviert/Deaktiviert, Intervall in Stunden. Manuell auslösbar per Button in den Einstellungen. Anzeigen jünger als 60 Minuten werden übersprungen.

---

## Benachrichtigungen & Automatisierung

### E-Mail-Alert (gebündelt)
Alle 15 Min. prüft der Notify-Job ob es neue (nicht gemeldete) Anzeigen gibt. Falls ja, wird eine gebündelte HTML-E-Mail versandt — strukturiert nach Plattform → Suchbegriff mit Inhaltsverzeichnis. Gratis-Items werden grün hervorgehoben. Jede Anzeige wird nur einmal gemeldet.

### Manueller Crawl
Per Knopfdruck im Dashboard: einzelne Plattform oder alle aktiven. Live-Log-Terminal zeigt den Fortschritt. Bei neuen Treffern wird sofort eine E-Mail versandt (unabhängig vom 15-Min.-Job).

### Tages-Digest
Täglich zur konfigurierten Uhrzeit (z.B. `19:00`) eine Zusammenfassung aller heute gefundenen Anzeigen als HTML-E-Mail. Unabhängig vom gebündelten Alert — eine Anzeige kann in beiden auftauchen.

### Pro-Plattform-Scheduler
Jede Plattform hat ihr eigenes konfigurierbares Crawl-Intervall. Der Scheduler läuft im Hintergrund — kein manueller Cronjob nötig.

---

## KI-Assistent

### Anfragetext-Generator
Im Detail-Modal per Klick auf „✨ Generieren" wird ein höflicher Kontakttext an den Verkäufer generiert. Der Text erscheint in einer editierbaren Textarea — nie automatisch gesendet.

### VB-Preisvorschlag
Bei Anzeigen mit „Verhandlungsbasis" schlägt die KI automatisch einen Preis vor: 85% des Durchschnittspreises aus den eigenen gesammelten Daten, auf 5 € gerundet.

### Persönliche Hinweise (`ai_prompt_hints`)
Eigene Instruktionen für alle generierten Texte, z.B. „Wir sind eine Familie mit zwei Kindern" oder „Keine Besichtigung bei Kleidung nötig". Werden an jeden Prompt angehängt.

### Modell-Selector
Dropdown mit vordefinierten Modellen nach Anbieter (Anthropic / OpenAI / Ollama). „🔄 Laden"-Button holt die aktuelle Modellliste direkt vom Anbieter. Provider wird automatisch am API-Key-Prefix erkannt (`sk-ant-` → Anthropic, `sk-` → OpenAI) — unabhängig vom eingetragenen Modellnamen.

### Betriebsmodi
| Modus | Konfiguration |
|-------|--------------|
| Anthropic (Cloud) | API-Key `sk-ant-…`, Modell wählen, Base-URL leer |
| OpenAI (Cloud) | API-Key `sk-…`, Modell wählen, Base-URL leer |
| Ollama (lokal) | Base-URL `http://ollama:11434/v1`, kein API-Key nötig |

---

## Admin-UI: Dashboard

| Element | Funktion |
|---------|----------|
| Suchbegriff-Sidebar | Hinzufügen, aktivieren/deaktivieren, löschen (inkl. Anzeigen), Preislimit pro Term, Filter-Klick |
| Plattform-Statustabelle | Status (✓ / ⟳ / deaktiviert), letzter Lauf, nächster Lauf, neue Anzeigen pro Plattform |
| Filter-Leiste | Sortierung, Altersfilter, Plattform, Entfernung, Gratis, Favoriten, Exclude-Freitext |
| Anzeigen-Karte | Bild, Titel, Preis, Standort, Entfernung, Badges; ★ Favorit, ✕ Dismiss, ↗ öffnen |
| Detail-Modal | Vollbild-Bild, Beschreibung, Notiz-Textarea, KI-Anfragetext-Generator |
| 🚀 Jetzt crawlen | Startet manuellen Crawl mit Live-Log; E-Mail bei neuen Treffern |
| 📊 Preisstatistik | Aufklappbare Tabelle mit Avg/Min/Max/Gratis pro Suchbegriff |
| Filter-Panel | Aus-/einklappbar; aktive Filter-Anzahl als Badge |

---

## Admin-UI: Einstellungen

Die Einstellungsseite ist in fünf Tabs gegliedert. Deaktivierte Plattformen werden optisch gedimmt. Der Speichern-Button ist sticky am Seitenende. Ungespeicherte Änderungen lösen einen Browser-Dialog beim Verlassen aus.

| Bereich | Tab | Konfigurierbar |
|---------|-----|---------------|
| Kleinanzeigen.de | Plattformen | Aktiviert, Max. Preis, Standort-Slug, Radius, Crawl-Intervall, Test-Button |
| Shpock | Plattformen | Aktiviert, Max. Preis, Standort, Radius (0 = kein Filter), Crawl-Intervall, Test-Button |
| Vinted | Plattformen | Aktiviert, Max. Preis, Standort, Radius (0 = kein Filter), Crawl-Intervall, Test-Button |
| eBay | Plattformen | Aktiviert, Max. Preis, Standort (PLZ oder Stadt), Radius, Crawl-Intervall, Test-Button |
| Facebook Marketplace | Plattformen | Aktiviert, Max. Preis, Standort, Crawl-Intervall |
| E-Mail | Benachrichtigungen | SMTP-Server/-Port, Absender, Empfänger (kommagetrennt), App-Passwort, Alert-Betreff |
| Tages-Digest | Benachrichtigungen | Aktiviert, Uhrzeit (`HH:MM`), Digest-Betreff |
| Crawler | Crawler & Daten | Max. Ergebnisse pro Suche, Pause zwischen Anfragen (s), Blacklist |
| Anzeigen-Verwaltung | Crawler & Daten | Altersfilter (Anzeige), Anzeigen löschen älter als X Stunden |
| Verfügbarkeits-Check | Crawler & Daten | Aktiviert, Intervall (Stunden), „Jetzt prüfen"-Button |
| Heimstandort | Crawler & Daten | Stadtname für Entfernungsberechnung |
| KI-Assistent | KI-Assistent | Aktiviert, API-Key, Modell (Selector + Live-Fetch), Persönliche Hinweise, Base-URL |
| Profile | Profile | Anlegen (Name + Emoji), umbenennen, löschen |

---

## API-Endpunkte

| Method | URL | Beschreibung |
|--------|-----|--------------|
| GET | `/` | Dashboard |
| GET | `/settings` | Einstellungsseite |
| POST | `/settings` | Einstellungen speichern |
| POST | `/terms` | Suchbegriff hinzufügen |
| POST | `/terms/<id>/delete` | Suchbegriff + Anzeigen löschen |
| POST | `/terms/<id>/toggle` | Aktivieren / Deaktivieren |
| POST | `/terms/<id>/max-price` | Preis-Schwelle setzen (`{"max_price": N}`) |
| POST | `/listings/<id>/favorite` | Favorit toggeln |
| POST | `/listings/<id>/dismiss` | Anzeige dauerhaft ausblenden |
| POST | `/listings/<id>/note` | Notiz setzen/löschen (`{"note": "..."}`) |
| GET | `/api/listings` | Anzeigen als JSON (`?term=`, `?platform=`, `?limit=`, `?offset=`, `?favorites=`, `?free=`, `?max_age=`, `?max_distance=`, `?sort=`, `?exclude=`) |
| GET | `/api/status` | Crawler-Status inkl. `platforms`-Array (Status, letzter/nächster Lauf, neue Anzeigen) |
| GET | `/api/stats` | Preisstatistik pro Suchbegriff (Avg/Min/Max/Gratis) |
| GET | `/api/platforms` | Distinct Plattformen der gespeicherten Anzeigen |
| GET | `/api/ai-models` | Modellliste vom konfigurierten Anbieter (Anthropic/OpenAI/Ollama) |
| POST | `/api/crawl` | Crawl manuell starten |
| POST | `/api/test-scraper` | Scraper-Verbindung testen (`{"platform": "kleinanzeigen"}`) |
| POST | `/api/listings/<id>/contact-text` | KI-Anfragetext generieren |
| POST | `/api/availability-check` | Verfügbarkeits-Check manuell starten |
| POST | `/api/clear-listings-by-age` | Anzeigen löschen + dismissen älter als X Stunden (`{"hours": N}`) |
| GET | `/profiles/select` | Profil-Auswahl (nur wenn Profile existieren) |
| POST | `/profiles/select/<id>` | Profil aktivieren |
| POST | `/profiles/logout` | Session leeren |
| POST | `/profiles` | Neues Profil anlegen |
| POST | `/profiles/<id>/update` | Profil umbenennen / Emoji ändern |
| POST | `/profiles/<id>/delete` | Profil löschen |

---

## Architektur

```
marktcrawler/
├── Dockerfile / docker-compose.yml / docker-compose.ollama.yml
├── requirements.txt / pytest.ini
├── run.py                  # Einstiegspunkt (Flask dev server + load_dotenv)
├── data/                   # Persistentes Volume (SQLite-DB, FB-Session)
├── docs/
│   └── screenshots/        # UI-Vorschaubilder
├── tests/                  # 388 Unit-Tests (alle ohne externe Abhängigkeiten)
│   ├── conftest.py
│   ├── test_crawler.py
│   ├── test_crawl_run.py
│   ├── test_database.py
│   ├── test_geo.py
│   ├── test_notifier.py
│   ├── test_routes.py
│   ├── test_scrapers.py
│   ├── test_checker.py
│   └── test_ai.py
└── app/
    ├── __init__.py         # Flask App Factory, DB + Scheduler initialisieren; SECRET_KEY-Persistenz
    ├── database/           # SQLite-Schicht (kein ORM), versioniertes Migrations-Framework
    │   ├── __init__.py     # Re-Exports aller öffentlichen Symbole
    │   ├── core.py         # DB-Pfad, get_db(), init_db(), Migrations
    │   ├── listings.py     # save_listing(), get_listings(), claim_unnotified_listings()
    │   ├── geocache.py     # Geocoding-Cache (lowercase-normalisiert)
    │   └── …               # settings, search_terms, profiles, stats
    ├── routes/             # Alle Flask-Routen & REST-API (Blueprint "main")
    │   ├── __init__.py     # Blueprint-Definition
    │   ├── views.py        # HTML-Routen (Dashboard, Settings, …)
    │   ├── api.py          # REST-API (/api/*)
    │   ├── profiles.py     # /profiles/*-Routen
    │   └── _helpers.py     # Plattform-Konstanten, build_platform_stats()
    ├── crawler.py          # Crawl-Orchestrierung (Thread-safe, threading.Lock)
    ├── checker.py          # Verfügbarkeits-Check (HEAD-Requests, Running-Guard)
    ├── scheduler.py        # APScheduler: Pro-Plattform-Crawl + Notify-Job + Digest + Checker
    ├── notifier.py         # SMTP: gebündelter Alert + Sofort (manuell) + Digest
    ├── ai.py               # KI-Assistent: Anfragetext + Provider-Erkennung (Claude/OpenAI/Ollama)
    ├── geo.py              # Nominatim-Geocoding + Haversine + DB-Cache
    ├── scrapers/
    │   ├── base.py         # Listing-Dataclass, BaseScraper ABC, Hilfsfunktionen
    │   ├── kleinanzeigen.py  # requests + BeautifulSoup
    │   ├── shpock.py         # GraphQL-API
    │   ├── vinted.py         # REST-API mit Session-Cookie; Altersfilter via created_at_ts
    │   ├── ebay.py           # requests + BeautifulSoup; URL-Encoding mit quote_plus
    │   └── facebook.py       # Playwright headless
    └── templates/
        ├── base.html              # Navbar, Flash-Messages, Tailwind
        ├── index.html             # Dashboard
        ├── settings.html          # Einstellungsformular (5 Tabs)
        ├── profiles_select.html   # Profil-Auswahl (Netflix-Stil)
        └── _listing_card.html     # Anzeigenkarte (Jinja2-Partial)
```

**Tech-Stack**: Python 3.12 · Flask 3 · APScheduler 3 · SQLite (kein ORM) · Tailwind CSS via CDN (kein Build-Step) · Gunicorn 1 Worker · Docker + docker-compose
