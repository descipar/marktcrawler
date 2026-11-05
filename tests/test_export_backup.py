"""Tests für Anzeigen-Export (CSV/JSON) und Settings-Backup (Export/Import)."""

import csv
import io
import json

import pytest


@pytest.fixture()
def app(tmp_path, monkeypatch):
    import app.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "")  # Scheduler nicht starten

    from app import create_app
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def _add(listing_id, title, platform="Kleinanzeigen", price="10 €", term="kinderwagen", **kw):
    from app.scrapers.base import Listing
    import app.database as db
    db.save_listing(Listing(
        platform=platform, title=title, price=price, location="München",
        url=f"https://example.com/{listing_id}", listing_id=listing_id,
        search_term=term, **kw,
    ))


def _parse_csv(resp):
    text = resp.data.decode("utf-8")
    assert text.startswith("﻿"), "CSV braucht BOM für Excel"
    return list(csv.DictReader(io.StringIO(text[1:]), delimiter=";"))


# ── Anzeigen-Export ───────────────────────────────────────────

class TestListingsExport:

    def test_csv_download_header(self, client):
        _add("e1", "Kinderwagen Bugaboo")
        resp = client.get("/api/listings/export?format=csv")
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        assert "attachment" in resp.headers["Content-Disposition"]
        assert ".csv" in resp.headers["Content-Disposition"]

    def test_csv_enthaelt_anzeigen(self, client):
        _add("e1", "Kinderwagen Bugaboo", description="Top Zustand")
        rows = _parse_csv(client.get("/api/listings/export?format=csv"))
        assert len(rows) == 1
        assert rows[0]["title"] == "Kinderwagen Bugaboo"
        assert rows[0]["url"] == "https://example.com/e1"
        assert rows[0]["description"] == "Top Zustand"

    def test_json_export(self, client):
        _add("e1", "Kinderwagen A")
        _add("e2", "Kinderwagen B")
        resp = client.get("/api/listings/export?format=json")
        assert resp.status_code == 200
        assert resp.mimetype == "application/json"
        data = json.loads(resp.data)
        assert {d["title"] for d in data} == {"Kinderwagen A", "Kinderwagen B"}
        assert "image_url" not in data[0]

    def test_default_format_ist_csv(self, client):
        resp = client.get("/api/listings/export")
        assert resp.mimetype == "text/csv"

    def test_ungueltiges_format(self, client):
        assert client.get("/api/listings/export?format=xml").status_code == 400

    def test_ungueltiger_filter(self, client):
        assert client.get("/api/listings/export?max_age=abc").status_code == 400

    def test_filter_werden_angewendet(self, client):
        _add("e1", "Kinderwagen", platform="Kleinanzeigen", term="kinderwagen")
        _add("e2", "Babybett", platform="Shpock", term="babybett")
        _add("e3", "Kinderwagen defekt", platform="Kleinanzeigen", term="kinderwagen")
        rows = _parse_csv(client.get(
            "/api/listings/export?format=csv&platform=Kleinanzeigen&term=kinderwagen&exclude=defekt"))
        assert [r["title"] for r in rows] == ["Kinderwagen"]

    def test_export_ignoriert_pagination(self, client):
        for i in range(45):
            _add(f"p{i}", f"Kinderwagen {i}")
        data = json.loads(client.get("/api/listings/export?format=json&limit=10").data)
        assert len(data) == 45

    def test_csv_formel_injection_wird_entschaerft(self, client):
        _add("e1", "=HYPERLINK(\"http://evil\")")
        rows = _parse_csv(client.get("/api/listings/export?format=csv"))
        assert rows[0]["title"].startswith("'=")

    def test_json_formel_bleibt_unveraendert(self, client):
        _add("e1", "=SUMME(A1)")
        data = json.loads(client.get("/api/listings/export?format=json").data)
        assert data[0]["title"] == "=SUMME(A1)"

    def test_leerer_export(self, client):
        rows = _parse_csv(client.get("/api/listings/export?format=csv"))
        assert rows == []

    def test_api_listings_weiterhin_paginiert(self, client):
        for i in range(5):
            _add(f"p{i}", f"Kinderwagen {i}")
        data = json.loads(client.get("/api/listings?limit=2").data)
        assert len(data) == 2


# ── Settings-Export ───────────────────────────────────────────

class TestSettingsExport:

    def test_export_format(self, client):
        resp = client.get("/api/settings/export")
        assert resp.status_code == 200
        assert "attachment" in resp.headers["Content-Disposition"]
        data = json.loads(resp.data)
        assert data["format"] == "marktcrawler-settings"
        assert data["version"] == 1
        assert data["includes_secrets"] is False
        assert "kleinanzeigen_enabled" in data["settings"]
        assert any(t["term"] == "kinderwagen" for t in data["search_terms"])

    def test_export_ohne_secrets(self, client):
        import app.database as db
        db.save_settings({"email_password": "geheim", "ai_api_key": "sk-ant-xyz"})
        data = json.loads(client.get("/api/settings/export").data)
        assert "email_password" not in data["settings"]
        assert "ai_api_key" not in data["settings"]

    def test_export_mit_secrets(self, client):
        import app.database as db
        db.save_settings({"email_password": "geheim", "ai_api_key": "sk-ant-xyz"})
        data = json.loads(client.get("/api/settings/export?secrets=1").data)
        assert data["includes_secrets"] is True
        assert data["settings"]["email_password"] == "geheim"
        assert data["settings"]["ai_api_key"] == "sk-ant-xyz"

    def test_export_ohne_status_keys(self, client):
        import app.database as db
        db.save_settings({"kleinanzeigen_last_crawl_end": "2026-01-01", "crawl_status": "running"})
        data = json.loads(client.get("/api/settings/export").data)
        assert "kleinanzeigen_last_crawl_end" not in data["settings"]
        assert "crawl_status" not in data["settings"]

    def test_export_term_max_price(self, client):
        import app.database as db
        db.add_search_term("tripp trapp")
        tid = next(t["id"] for t in db.get_search_terms() if t["term"] == "tripp trapp")
        db.update_term_max_price(tid, 40)
        data = json.loads(client.get("/api/settings/export").data)
        entry = next(t for t in data["search_terms"] if t["term"] == "tripp trapp")
        assert entry == {"term": "tripp trapp", "enabled": True, "max_price": 40}


# ── Settings-Import ───────────────────────────────────────────

def _payload(settings=None, terms=None, **kw):
    p = {"format": "marktcrawler-settings", "version": 1,
         "settings": settings or {}, "search_terms": terms or []}
    p.update(kw)
    return p


class TestSettingsImport:

    def _post(self, client, payload):
        return client.post("/api/settings/import", json=payload)

    def test_import_setzt_werte(self, client):
        import app.database as db
        resp = self._post(client, _payload({"kleinanzeigen_max_price": "55", "home_location": "Dortmund"}))
        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["settings_imported"] == 2
        s = db.get_settings()
        assert s["kleinanzeigen_max_price"] == "55"
        assert s["home_location"] == "Dortmund"

    def test_import_ignoriert_unbekannte_keys(self, client):
        import app.database as db
        resp = self._post(client, _payload({"crawl_status": "running", "evil_key": "x", "digest_time": "07:30"}))
        body = json.loads(resp.data)
        assert set(body["skipped"]) == {"crawl_status", "evil_key"}
        s = db.get_settings()
        assert s["crawl_status"] == "idle"
        assert "evil_key" not in s
        assert s["digest_time"] == "07:30"

    def test_import_bool_normalisierung(self, client):
        import app.database as db
        self._post(client, _payload({"vinted_enabled": True, "shpock_enabled": "0",
                                     "willhaben_paylivery_only": 0}))
        s = db.get_settings()
        assert s["vinted_enabled"] == "1"
        assert s["shpock_enabled"] == "0"
        assert s["willhaben_paylivery_only"] == "0"

    def test_import_zahlen_als_string(self, client):
        import app.database as db
        self._post(client, _payload({"ebay_radius": 25}))
        assert db.get_settings()["ebay_radius"] == "25"

    def test_leere_secrets_ueberschreiben_nicht(self, client):
        import app.database as db
        db.save_settings({"email_password": "geheim"})
        self._post(client, _payload({"email_password": ""}))
        assert db.get_settings()["email_password"] == "geheim"

    def test_secrets_werden_gesetzt(self, client):
        import app.database as db
        self._post(client, _payload({"ai_api_key": "sk-neu"}))
        assert db.get_settings()["ai_api_key"] == "sk-neu"

    def test_import_ergaenzt_suchbegriffe(self, client):
        import app.database as db
        before = {t["term"] for t in db.get_search_terms()}
        resp = self._post(client, _payload(terms=[
            {"term": "tripp trapp", "enabled": False, "max_price": 30},
            {"term": "kinderwagen", "enabled": False},   # existiert schon → unverändert
            {"term": "  "},                               # leer → ignoriert
        ]))
        assert json.loads(resp.data)["terms_added"] == 1
        terms = {t["term"]: t for t in db.get_search_terms()}
        assert terms["tripp trapp"]["enabled"] == 0
        assert terms["tripp trapp"]["max_price"] == 30
        assert set(terms) == before | {"tripp trapp"}
        if "kinderwagen" in before:
            assert terms["kinderwagen"]["enabled"] == 1

    def test_import_ungueltiger_max_price(self, client):
        import app.database as db
        self._post(client, _payload(terms=[{"term": "wippe", "max_price": "abc"}]))
        t = next(t for t in db.get_search_terms() if t["term"] == "wippe")
        assert t["max_price"] is None

    @pytest.mark.parametrize("payload", [
        None,
        [],
        {"format": "anderes-tool", "version": 1},
        {"format": "marktcrawler-settings"},
        {"format": "marktcrawler-settings", "version": 99},
        {"format": "marktcrawler-settings", "version": 1, "settings": ["x"]},
        {"format": "marktcrawler-settings", "version": 1, "search_terms": "x"},
    ])
    def test_ungueltige_dateien(self, client, payload):
        if payload is None:
            resp = client.post("/api/settings/import", data="kein json", content_type="application/json")
        else:
            resp = self._post(client, payload)
        assert resp.status_code == 400
        assert "error" in json.loads(resp.data)

    def test_roundtrip(self, client):
        import app.database as db
        db.save_settings({"marktde_radius": "77", "crawler_blacklist": "defekt\nkaputt"})
        db.add_search_term("beistellbett")
        exported = json.loads(client.get("/api/settings/export").data)

        db.save_settings({"marktde_radius": "10", "crawler_blacklist": ""})
        resp = self._post(client, exported)
        assert resp.status_code == 200
        s = db.get_settings()
        assert s["marktde_radius"] == "77"
        assert s["crawler_blacklist"] == "defekt\nkaputt"
        assert any(t["term"] == "beistellbett" for t in db.get_search_terms())


class TestSettingsFormUnchanged:
    """Refactoring-Absicherung: Formular-Speichern nutzt weiterhin dieselben Keys."""

    def test_checkbox_nicht_gesetzt_wird_0(self, client):
        import app.database as db
        client.post("/settings", data={"kleinanzeigen_max_price": "42"})
        s = db.get_settings()
        assert s["kleinanzeigen_max_price"] == "42"
        assert s["kleinanzeigen_enabled"] == "0"
        assert s["willhaben_paylivery_only"] == "0"

    def test_checkbox_gesetzt_wird_1(self, client):
        import app.database as db
        client.post("/settings", data={"vinted_enabled": "on", "crawler_lang_filter_enabled": "on"})
        s = db.get_settings()
        assert s["vinted_enabled"] == "1"
        assert s["crawler_lang_filter_enabled"] == "1"
