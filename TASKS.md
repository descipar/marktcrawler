# 📋 Marktcrawler – Aufgaben & Roadmap

Die vollständige Geschichte aller abgeschlossenen Phasen (1–24) findet sich in [TASKS_v1.0.md](TASKS_v1.0.md) (Stand: Release v1.0.0).

---

## ✅ Abgeschlossene Phasen (seit v1.0)

### Phase 25 – UX-Verbesserungen & Info-Seite

- [x] Preisstatistik (per Suchbegriff) von Dashboard auf Info-Seite verschoben — passt besser zur dortigen Analyse-Ansicht
- [x] `get_price_stats()` in `test_database.py` durch 5 Unit-Tests abgedeckt (leere DB, Aggregation, mehrere Terme, ungültige Preise, Gratis-Zähler)
- [x] E-Mail-Benachrichtigung: „Im Dashboard →"-Button pro Anzeige mit Deep-Link `/?modal=<db_id>` — öffnet Modal direkt beim Seitenload
- [x] `server_url`-Eingabe in Settings tolerant: IP oder Hostname reicht (`192.168.1.10`, `raspberrypi.local`), `http://` und `:5000` werden automatisch ergänzt; `_normalize_server_url()` mit 8 Unit-Tests abgedeckt
- [x] Settings: Datenverwaltungs-Block in eigenen Tab „🗑️ Daten" verschoben; Speichern-Button auf diesem Tab ausgeblendet
- [x] Info-Seite: aktuellen Commit (Hash, Datum, Message) und verfügbare GitHub-Updates anzeigen; `app/version.py` liest `.git` beim `docker build` via `scripts/bake_version.py` ein — kein Build-Arg, kein Script nötig, `git pull && docker compose up -d --build` reicht
- [x] Update-Check auf On-Demand-Button umgestellt (war Auto-Load); Commit-Hashes auf Info-Seite als GitHub-Links; Repo-URL im Check-Updates-Response
- [x] `_last_commit_from_log()` in `bake_version.py` filtert "Fast-forward"-/Checkout-Einträge aus dem `.git/logs`-Branch-Log heraus — zeigt korrekte letzte Commit-Message statt "Fast-forward"
- [x] 11 weitere Tests (`TestLastCommitFromLog` × 6, `TestCheckUpdatesApi` × 6) — gesamt 430

---

### Phase 27 – Neue Plattformen: Willhaben.at & markt.de

- [x] **WillhabenScraper** (`app/scrapers/willhaben.py`): `__NEXT_DATA__`-JSON-Parsing (Next.js SSR), `_attr()`-Hilfsfunktion für Attributlisten, PayLivery-Parameter (Versand-Only, Default aktiv), Haversine-Radius wenn PayLivery deaktiviert
- [x] **MarktdeScraper** (`app/scrapers/markt.py`): BeautifulSoup HTML, `_city_slug()` mit Umlaut-Normalisierung, Radius als URL-Parameter, Pagination
- [x] Beide in `PLATFORM_SCRAPER_MAP` + `DEFAULT_INTERVALS` + `scrapers/__init__.py` eingetragen
- [x] `DEFAULT_SETTINGS` in `core.py` ergänzt (willhaben_*, marktde_*)
- [x] Settings-Formular: neue Plattform-Abschnitte mit PayLivery-Checkbox und Hinweistext
- [x] `allowed_keys` in `views.py` + `test-scraper`-Endpoint in `api.py` aktualisiert
- [x] Fix: `crawler_lang_filter_enabled` und `willhaben_paylivery_only` als Checkboxen korrekt behandelt
- [x] 26 neue Tests (519 gesamt)
- [x] **100% Testabdeckung** aller 6 Scraper (ebay, kleinanzeigen, markt, shpock, vinted, willhaben): 49 neue Coverage-Tests, Fix `except Exception` in `kleinanzeigen.py` — 568 Tests gesamt

---

### Phase 26 – Crawl-Qualität

- [x] **Wortgrenzen-Matching**: `_matches_all_words()` nutzt jetzt `\b`-Regex statt Substring-Suche — verhindert False-Positives wie „werder" → „Schwerder" oder „body" → „somebody". Cleanup-Script ebenfalls aktualisiert.
- [x] **Sprachfilter**: Neues Setting `crawler_lang_filter_enabled` + `crawler_lang_filter_langs` (Default `de`). Anzeigen in nicht erlaubten Sprachen werden via `langdetect` herausgefiltert. Texte < 20 Zeichen und Erkennungsfehler werden durchgelassen. Settings-Tab Crawler.
- [x] **Auto-Cleanup nicht passender Anzeigen**: `db.cleanup_mismatched_listings()` entfernt alle Anzeigen, deren Titel+Beschreibung nicht alle Wörter des Suchbegriffs enthalten, und trägt sie als dismissed ein. Läuft einmalig als v9-Migration beim ersten Start nach Update. Manuell auslösbar über `POST /api/cleanup-mismatched` + Button im Daten-Tab.
- [x] **Verfügbarkeits-Timestamp auf Karte**: Zeitpunkt der letzten Verfügbarkeitsprüfung als Klartext direkt auf der Anzeigenkarte (kein Badge) — „Verfügbarkeit geprüft: vor 2h" oder „Verfügbarkeit noch nicht geprüft". Mit relativem Zeitformat via `initRelativeTimes()`.
- [x] 32 neue Tests (462 gesamt)

---

## 🔜 Offene Aufgaben

Zum Umsetzen einfach den Kategorienamen nennen (z.B. „mach Tastaturkürzel") oder einzelne Tasks per Nummer (z.B. „mach 11 und 21").

---

### Features – KI-Integration

**Option B – Listing-Bewertung (Score 1–10)**
- [ ] Beim Crawl: Claude bewertet jedes neue Listing anhand von Titel + Beschreibung (Relevanz, Preis-Leistung, Zustand)
- [ ] Score wird in DB gespeichert (neues Feld `ai_score`), im Dashboard als Badge angezeigt
- [ ] Dashboard: nach Score sortieren/filtern
- [ ] Nur neue Listings werden bewertet (kein Re-Scoring bestehender)

**Option C – Smarte Benachrichtigung**
- [ ] E-Mail/Notify-Job sendet nur Listings ab konfiguriertem Mindest-Score (z.B. ≥ 7)
- [ ] Einstellung `ai_notify_min_score` in Settings
- [ ] Abhängig von Option B (Score muss vorhanden sein)

**Option D – Zustand & Details extrahieren**
- [ ] KI extrahiert aus Beschreibung: Zustand (neu/gut/gebraucht/defekt), Altersangabe, enthaltenes Zubehör
- [ ] Strukturiert gespeichert, filtert "defekt"-Anzeigen zuverlässiger als die aktuelle Keyword-Blacklist
- [ ] Wird als Tooltip/Badge im Dashboard angezeigt

**Option E – Duplikat-Erkennung verbessern**
- [ ] Aktueller Ansatz: einfacher String-Vergleich des Titelanfangs
- [ ] KI-gestützt: erkennt semantische Duplikate auch bei unterschiedlichen Titeln

**Sonstiges KI**
- [ ] Install-Script (fragt ab ob Ollama gewünscht, erkennt Hardware/Arch)

---

### Features – Benachrichtigungen

- [ ] **12** – Telegram-Bot als Alternative zu SMTP (Bot-Token + Chat-ID, Alert + Digest)
- [ ] **20** – Browser Push Notifications (Web Push API, kein E-Mail-Setup nötig)

---

### Features – Daten & Export

- [ ] **13** – CSV/JSON-Export der aktuell gefilterten Anzeigen (clientseitiger Download)
- [ ] **23** – Settings-Backup: Import/Export als JSON-Datei

---

### Features – Komfort & Bedienung

- [ ] **11** – Tastaturkürzel: j/k navigieren, f favorisieren, d dismisssen, / Suche fokussieren, ? Hilfe-Overlay
- [ ] **21** – Dark Mode (`prefers-color-scheme` + manueller Toggle, Zustand in `localStorage`)
- [ ] **22** – PWA-Manifest: App auf Smartphone installierbar (Homescreen-Icon, Offline-Splash)
