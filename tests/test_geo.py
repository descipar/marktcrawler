"""Tests für app/geo.py: haversine() und distance_to_home()."""

import pytest
import threading
from unittest.mock import patch, MagicMock

from app.geo import haversine, distance_to_home


# ── haversine ────────────────────────────────────────────────

class TestHaversine:
    def test_gleicher_punkt_ist_null(self):
        """Distanz von einem Punkt zu sich selbst = 0."""
        assert haversine(51.5, 7.5, 51.5, 7.5) == pytest.approx(0.0, abs=1e-6)

    def test_dortmund_nach_berlin(self):
        """Bekannte Distanz Dortmund → Berlin ≈ 421 km (Luftlinie)."""
        dist = haversine(51.5136, 7.4653, 52.5200, 13.4050)
        assert 415 < dist < 430

    def test_dortmund_nach_koeln(self):
        """Bekannte Distanz Dortmund → Köln ≈ 75 km."""
        dist = haversine(51.5136, 7.4653, 50.9333, 6.9500)
        assert 70 < dist < 82

    def test_symmetrie(self):
        """haversine(A, B) == haversine(B, A)."""
        d1 = haversine(51.5136, 7.4653, 52.5200, 13.4050)
        d2 = haversine(52.5200, 13.4050, 51.5136, 7.4653)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_positive_distanz(self):
        """Distanz ist immer positiv (auch wenn lon2 < lon1)."""
        dist = haversine(52.5200, 13.4050, 51.5136, 7.4653)
        assert dist > 0


# ── distance_to_home ─────────────────────────────────────────

class TestDistanceToHome:
    SETTINGS = {
        "home_latitude": "51.5136",
        "home_longitude": "7.4653",
    }

    def test_gibt_distanz_zurueck_wenn_geocoding_klappt(self, temp_db):
        """Wenn geocode() einen Treffer liefert, wird die Haversine-Distanz zurückgegeben."""
        with patch("app.geo.geocode", return_value=(52.5200, 13.4050)) as mock_gc:
            result = distance_to_home("Berlin", self.SETTINGS)
            mock_gc.assert_called_once_with("Berlin")
            assert result is not None
            assert 415 < result < 430

    def test_gibt_none_zurueck_wenn_geocoding_fehlschlaegt(self, temp_db):
        """Wenn geocode() None zurückgibt, ist das Ergebnis ebenfalls None."""
        with patch("app.geo.geocode", return_value=None):
            result = distance_to_home("UnbekannterOrt123", self.SETTINGS)
            assert result is None

    def test_gibt_none_wenn_heimkoordinaten_fehlen(self, temp_db):
        """Ohne Heimkoordinaten kann keine Distanz berechnet werden."""
        settings_ohne_home = {}
        result = distance_to_home("Berlin", settings_ohne_home)
        assert result is None

    def test_gibt_none_wenn_heimkoordinaten_leer(self, temp_db):
        """Leere Heimkoordinaten (nicht konfiguriert) → None."""
        settings = {"home_latitude": "", "home_longitude": ""}
        with patch("app.geo.geocode", return_value=(52.5200, 13.4050)):
            result = distance_to_home("Berlin", settings)
            assert result is None

    def test_koordinaten_null_null_sind_gueltig(self, temp_db):
        """Koordinaten 0.0/0.0 (Äquator/Nullmeridian) sind gültige Heimkoordinaten."""
        settings = {"home_latitude": "0", "home_longitude": "0"}
        with patch("app.geo.geocode", return_value=(52.5200, 13.4050)):
            result = distance_to_home("Berlin", settings)
            assert result is not None

    def test_fallback_auf_koordinaten(self, temp_db):
        """Wenn home_location fehlt, werden home_latitude/longitude als Fallback verwendet."""
        settings = {
            "home_latitude": "51.5136",
            "home_longitude": "7.4653",
        }
        with patch("app.geo.geocode", return_value=(52.5200, 13.4050)):
            result = distance_to_home("Berlin", settings)
            assert result is not None
            assert 415 < result < 430

    def test_home_location_als_stadtname(self, temp_db):
        """home_location als Stadtname wird geocodiert und für Distanzberechnung genutzt."""
        settings = {"home_location": "München"}
        with patch("app.geo.geocode", side_effect=lambda loc: (48.1351, 11.5820)):
            result = distance_to_home("Berlin", settings)
            assert result is not None


# ── geocode (Cache-Verhalten) ─────────────────────────────────

class TestGeocodeCache:
    def test_cache_hit_verhindert_nominatim_aufruf(self, temp_db):
        """Wenn der Ort im DB-Cache ist, wird kein HTTP-Request gemacht."""
        # Erst in den Cache schreiben
        temp_db.save_geocache("Dortmund", 51.5136, 7.4653)

        with patch("app.geo.requests.get") as mock_get:
            from app.geo import geocode
            result = geocode("Dortmund")
            mock_get.assert_not_called()
            assert result == pytest.approx((51.5136, 7.4653), abs=1e-4)

    def test_cache_miss_ruft_nominatim_auf(self, temp_db):
        """Bei Cache-Miss wird Nominatim aufgerufen und das Ergebnis gecacht."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"lat": "51.5136", "lon": "7.4653"}]

        with patch("app.geo.requests.get", return_value=mock_response) as mock_get:
            with patch("app.geo.time.sleep"):  # Rate-Limit-Sleep überspringen
                from app.geo import geocode
                result = geocode("Dortmund Neu")
                mock_get.assert_called_once()
                assert result == pytest.approx((51.5136, 7.4653), abs=1e-4)

        # Ergebnis sollte jetzt im Cache sein
        cached = temp_db.get_geocache("Dortmund Neu")
        assert cached is not None

    def test_kurzer_text_gibt_none_zurueck(self, temp_db):
        """Ortstexte mit weniger als 3 Zeichen werden nicht geokodiert."""
        from app.geo import geocode
        assert geocode("AB") is None
        assert geocode("") is None


class TestGeocodeConcurrency:

    def test_parallele_anfragen_verschiedene_staedte(self, temp_db):
        """Zwei gleichzeitige geocode()-Aufrufe für verschiedene Städte liefern je ein Ergebnis."""
        from app.geo import geocode

        call_count = 0
        results = {}
        lock = threading.Lock()

        def fake_nominatim(url, **kwargs):
            nonlocal call_count
            with lock:
                call_count += 1
            resp = MagicMock()
            if "Dortmund" in url:
                resp.json.return_value = [{"lat": "51.5136", "lon": "7.4653"}]
            else:
                resp.json.return_value = [{"lat": "48.1351", "lon": "11.5820"}]
            return resp

        barrier = threading.Barrier(2)

        def geocode_city(city):
            barrier.wait()
            results[city] = geocode(city)

        with patch("app.geo.requests.get", side_effect=fake_nominatim):
            with patch("app.geo.time.sleep"):
                threads = [
                    threading.Thread(target=geocode_city, args=("Dortmund NRW",)),
                    threading.Thread(target=geocode_city, args=("München Bayern",)),
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=5)

        assert results["Dortmund NRW"] is not None
        assert results["München Bayern"] is not None

    def test_cache_verhindert_doppelten_nominatim_aufruf(self, temp_db):
        """Ein bereits gecachter Ort löst keinen zweiten Nominatim-Request aus."""
        from app.geo import geocode

        temp_db.save_geocache("Berlin Mitte", 52.5200, 13.4050)

        with patch("app.geo.requests.get") as mock_get:
            geocode("Berlin Mitte")
            geocode("Berlin Mitte")
            mock_get.assert_not_called()
