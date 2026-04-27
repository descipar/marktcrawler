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
- [x] 13 neue Tests — gesamt 419

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
