# 🔍 Marktcrawler

Siehst du eine Anzeige für einen günstigen Kinderwagen — aber immer zu spät? **Marktcrawler** durchsucht Kleinanzeigen.de, Shpock, Vinted, eBay und Facebook Marketplace automatisch nach deinen Suchbegriffen und schickt dir eine E-Mail, sobald neue Treffer auftauchen.

Selbst gehostet, Docker-ready, läuft unbeaufsichtigt auf einem Raspberry Pi.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?logo=flask)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-442%20passed-brightgreen?logo=pytest)
![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)

---

<img src="docs/screenshots/dashboard.png" width="700" alt="Dashboard">

📁 [Alle Screenshots ansehen](docs/screenshots/)

---

## ✨ Features

### Suche & Crawler
- **5 Plattformen gleichzeitig**: Kleinanzeigen.de, Shpock, Vinted, eBay, Facebook Marketplace
- **Suchbegriffe** mit optionalem Preislimit pro Begriff; Blacklist für Ausschluss-Keywords (z.B. „defekt", „bastler")
- **Pro-Plattform-Scheduler** — jede Plattform hat ihr eigenes Crawl-Intervall, kein Cronjob nötig
- **Radius-Filter** mit Standort-Geocoding via OpenStreetMap; Radius 0 = kein Filter

### Benachrichtigungen
- **E-Mail-Alert (gebündelt)** — alle neuen Anzeigen alle 15 Min. kompakt per E-Mail, strukturiert nach Plattform und Suchbegriff
- **Tages-Digest** — tägliche Zusammenfassung zur konfigurierten Uhrzeit
- **Manueller Crawl** — per Knopfdruck mit Live-Log-Terminal und sofortiger Benachrichtigung

### Anzeigen & KI
- **✨ KI-Anfragetext** — generiert per Klick einen Kontakttext an den Verkäufer; bei VB-Anzeigen mit automatischem Preisvorschlag
- **⭐ Favoriten & Notizen** — Anzeigen markieren und kommentieren; Favoriten werden nie automatisch gelöscht
- **👤 Mehrbenutzer-Profile** — jedes Profil sieht „✨ Neu"-Badge für Anzeigen seit dem letzten Besuch
- **Duplikat-Erkennung & Dismiss** — plattformübergreifend; dauerhaft ausgeblendete Anzeigen erscheinen nie wieder
- **🔗 E-Mail-Deep-Link** — jede Anzeige in der Benachrichtigung hat einen „Im Dashboard →"-Button, der das Modal direkt öffnet
- **📊 Version & Update-Check** — Info-Seite zeigt den aktuell laufenden Commit und listet neuere Commits aus GitHub auf

📄 [Vollständige Feature-Dokumentation](docs/features.md)

---

## Schnellstart (Docker)

```bash
git clone https://github.com/descipar/marktcrawler.git
cd marktcrawler
docker compose up -d --build
```

Admin-UI aufrufen: **`http://localhost:5000`**

Bestehende Datenbanken werden automatisch migriert — keine Daten gehen verloren.

---

## 🤖 KI-Assistent einrichten

Der KI-Assistent generiert im Anzeigen-Modal per Klick auf „✨ Generieren" einen fertigen Anfragetext an den Verkäufer. Bei VB-Anzeigen schlägt er automatisch einen Preis vor — basierend auf dem Durchschnitt der eigenen gesammelten Daten. Der Text erscheint immer in einer **editierbaren Textarea** und wird nie automatisch gesendet.

### Option 1: Cloud-API (empfohlen)

Günstig und ohne lokale Ressourcen. Ein Anfragetext kostet ca. **0,00005 €** mit Claude Haiku.

**Anthropic (Claude):**
1. API-Key erstellen: [console.anthropic.com](https://console.anthropic.com)
2. In **Einstellungen → KI-Assistent** eintragen:
   - API-Key: `sk-ant-…`
   - Modell: aus Dropdown wählen oder „🔄 Laden" für aktuelle Liste
   - Base-URL: *(leer lassen)*

**OpenAI:**
- API-Key: `sk-…` · Modell: `gpt-4o-mini` · Base-URL: *(leer lassen)*

### Option 2: Lokal via Ollama

Vollständig offline, kein API-Key nötig.

> ⚠️ **Nicht für Raspberry Pi 4 geeignet.** CPU-only bedeutet 2–5 Min. pro Antwort. Für den RPi4 empfehlen wir Option 1.

```bash
# Ollama als zweiten Container starten
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d

# Modell laden (einmalig, ~1,6 GB)
docker exec marktcrawler-ollama ollama pull gemma2:2b
```

Dann in **Einstellungen → KI-Assistent**: Modell `gemma2:2b`, Base-URL `http://ollama:11434/v1`, API-Key leer.

| Modell | Größe | RAM-Bedarf |
|--------|-------|------------|
| `gemma2:2b` | 1,6 GB | 4 GB |
| `phi3:mini` | 2,3 GB | 6 GB |
| `qwen2.5:0.5b` | 400 MB | 2 GB |

---

## 📧 E-Mail einrichten

### Gmail

1. [App-Passwort erstellen](https://myaccount.google.com/apppasswords) (2FA muss aktiv sein)
2. In **Einstellungen → Benachrichtigungen** eintragen:
   - SMTP-Server: `smtp.gmail.com` · Port: `587`
   - Absender: `deine-adresse@gmail.com`
   - App-Passwort: *(das erzeugte App-Passwort)*
   - Empfänger: `du@example.com, partner@example.com` (kommagetrennt)

### Weitere Anbieter

| Anbieter | SMTP-Server | Port |
|----------|-------------|------|
| GMX | mail.gmx.net | 587 |
| Web.de | smtp.web.de | 587 |
| Outlook | smtp.office365.com | 587 |

---

## 🚀 Deployment

### Docker (empfohlen)

```bash
docker compose up -d --build   # Starten
docker compose logs -f          # Logs ansehen
docker compose down             # Stoppen
git pull && docker compose up -d --build  # Update
```

### Raspberry Pi 4

Stromsparend (~5 Watt), läuft still 24/7:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker pi
git clone https://github.com/descipar/marktcrawler.git /home/pi/marktcrawler
cd /home/pi/marktcrawler
docker compose up -d --build
```

### Lokal (ohne Docker)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py                   # http://localhost:5000
```

### Facebook Marketplace (optional)

Einmaliger interaktiver Login nötig:

```bash
docker exec -it marktcrawler python -c \
  "from app.scrapers.facebook import FacebookScraper; FacebookScraper({}).interactive_login()"
```

> ⚠️ Das automatische Auslesen von Facebook widerspricht den Nutzungsbedingungen. Nur für den privaten Gebrauch.

---

## 🔧 Entwicklung & Tests

```bash
python -m pytest tests/ -v         # alle 442 Tests
python -m pytest tests/test_database.py -v  # einzelne Datei
```

Alle Tests laufen ohne externe Abhängigkeiten (HTTP und DB werden gemockt).

**Tech-Stack**: Python 3.12 · Flask 3 · APScheduler 3 · SQLite · Tailwind CSS (CDN) · Docker + Gunicorn

---

## 💾 Backup

```bash
cp ./data/baby_crawler.db ./backup_$(date +%Y%m%d).db
```

Anzeigen älter als 30 Tage werden automatisch bereinigt. **Favoriten werden dabei nie gelöscht.**

---

## 🧹 Datenpflege

### Anzeigen gegen Suchbegriffe bereinigen

Bei Mehrwort-Suchbegriffen (z.B. „baby werder") prüft der Crawler seit v1.1 ob **alle** Wörter in Titel oder Beschreibung vorkommen. Anzeigen, die vor diesem Update gespeichert wurden, können mit folgendem Script nachträglich bereinigt werden:

```bash
# Bericht: zeigt nicht passende Anzeigen gruppiert nach Suchbegriff
DATA_DIR=./data python scripts/cleanup_mismatched_listings.py

# Löschen: entfernt nicht passende Anzeigen und trägt sie als dismissed ein
DATA_DIR=./data python scripts/cleanup_mismatched_listings.py --delete
```

Gelöschte Anzeigen werden in `dismissed_listings` eingetragen und tauchen beim nächsten Crawl nicht erneut auf.

---

## 📄 Lizenz

[Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)

Frei nutzbar für private und nicht-kommerzielle Zwecke. Kommerzielle Nutzung nicht gestattet.

---

*Viel Erfolg bei der Schnäppchenjagd! 🔍*
