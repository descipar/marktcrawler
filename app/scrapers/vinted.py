"""Scraper für Vinted via Katalog-Suchseite.

Die frühere JSON-API ``/api/v2/catalog/items`` liefert seit 11/2026 nur noch
404. Die Suchseite ``/catalog?search_text=…`` ist eine Next.js-App, die die
Suchergebnisse serverseitig als React-Server-Components-Payload
(``self.__next_f.push([1, "…"])``) mitliefert. Darin steckt ein
``"items":{"items":[…]}``-Objekt mit Titel, Preis, URL und Fotos je Artikel.

Nicht mehr enthalten sind ``created_at_ts`` (→ ``vinted_max_age_hours`` greift
nur noch, falls Vinted das Feld wieder liefert) und die Stadt des Verkäufers
(→ der Radius-Filter wird übersprungen, wenn keine Stadt bekannt ist).
"""

from collections import OrderedDict
import json
import logging
import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing, _float, _int
from ..geo import geocode, haversine

logger = logging.getLogger(__name__)

CATALOG_URL = "https://www.vinted.de/catalog"
BASE_URL = "https://www.vinted.de"
_RSC_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
_ITEMS_MARKER_RE = re.compile(r'"items":\s*(?=\{\s*"items":)')
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9",
    "Referer": "https://www.vinted.de/",
}

_DETAIL_HEAD_MAX_BYTES = 256 * 1024
_DESCRIPTION_CACHE_MAX_ITEMS = 2000
_description_cache: "OrderedDict[str, str]" = OrderedDict()


class VintedScraper(BaseScraper):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.max_price: Optional[float] = _float(settings.get("vinted_max_price"))
        raw = _int(settings.get("vinted_radius", "30"))
        self.radius_km: int = 30 if raw is None else raw
        self._home: Optional[tuple] = self._resolve_location(settings)
        max_age_raw = _int(settings.get("vinted_max_age_hours", "48"))
        self.max_age_hours: int = max_age_raw if max_age_raw else 0
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._authenticate()

    @staticmethod
    def _resolve_location(settings: dict) -> Optional[tuple]:
        city = settings.get("vinted_location", "").strip()
        if city:
            coords = geocode(city)
            if coords:
                return coords
            logger.warning(f"[Vinted] Stadtname '{city}' konnte nicht geocodiert werden.")
        return None

    def _authenticate(self) -> bool:
        """Holt anonym ausgestellte JWT-Cookies (access_token_web) von der Startseite."""
        try:
            resp = self.session.get(BASE_URL, timeout=15)
            if not resp.ok:
                logger.warning(f"[Vinted] Authentifizierung: HTTP {resp.status_code} – Cookies ggf. ungültig.")
                return False
            return True
        except Exception as e:
            logger.warning(f"[Vinted] Authentifizierung fehlgeschlagen: {e}")
            return False

    @staticmethod
    def _cached_description(url: str) -> Optional[str]:
        description = _description_cache.get(url)
        if description is not None:
            _description_cache.move_to_end(url)
        return description

    @staticmethod
    def _cache_description(url: str, description: str) -> None:
        _description_cache[url] = description
        _description_cache.move_to_end(url)
        while len(_description_cache) > _DESCRIPTION_CACHE_MAX_ITEMS:
            _description_cache.popitem(last=False)

    def _fetch_detail_description(self, url: str, title: str) -> str:
        """Liest nur den HTML-Kopf einer Vinted-Detailseite aus.

        Die Katalog-API liefert üblicherweise keine Beschreibung. Im
        ``meta[name=description]`` der Detailseite ist sie dagegen enthalten.
        Der Stream wird nach dem ``</head>`` geschlossen, damit nicht die bis zu
        mehrere MB große vollständige Seite geladen werden muss.
        """
        if not url.startswith(f"{BASE_URL}/items/"):
            return ""

        cached = self._cached_description(url)
        if cached is not None:
            return cached

        for attempt in range(2):
            response = None
            try:
                response = self.session.get(url, timeout=15, stream=True)
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(chunk_size=16 * 1024):
                    if not chunk:
                        continue
                    content.extend(chunk)
                    if b"</head>" in content.lower() or len(content) >= _DETAIL_HEAD_MAX_BYTES:
                        break

                encoding = response.encoding or "utf-8"
                soup = BeautifulSoup(bytes(content).decode(encoding, errors="replace"), "lxml")
                meta = soup.find("meta", attrs={"name": "description"})
                raw = (meta.get("content", "") if meta else "").strip()
                prefix = f"{title.strip()} - "
                description = raw[len(prefix):].strip() if raw.startswith(prefix) else raw
                if description and description != title.strip():
                    self._cache_description(url, description)
                    return description
            except Exception as e:
                logger.debug(
                    f"[Vinted] Detailbeschreibung für '{title}' nicht geladen "
                    f"(Versuch {attempt + 1}/2): {e}"
                )
            finally:
                if response is not None:
                    response.close()
            if attempt == 0:
                time.sleep(0.25)
        return ""

    def enrich_listing(self, listing: Listing) -> Listing:
        description = self._fetch_detail_description(listing.url, listing.title)
        if description:
            listing.description = description
        return listing

    @staticmethod
    def _extract_catalog_items(html: str) -> List[dict]:
        """Liest die Suchergebnisse aus dem RSC-Payload der Katalogseite.

        Wirft ``ValueError``, wenn kein Ergebnis-Objekt gefunden wird – dann hat
        Vinted vermutlich das Seitenformat geändert.
        """
        parts = []
        for raw in _RSC_PUSH_RE.findall(html):
            try:
                parts.append(json.loads(f'"{raw}"'))
            except ValueError:
                continue
        blob = "".join(parts)
        match = _ITEMS_MARKER_RE.search(blob)
        if not match:
            raise ValueError("Keine Suchergebnisse im Seiten-Payload gefunden (Format geändert?)")
        container, _ = json.JSONDecoder().raw_decode(blob, match.end())
        return [VintedScraper._normalize(entry) for entry in container.get("items") or []]

    @staticmethod
    def _normalize(entry: dict) -> dict:
        """Bringt einen Katalog-Eintrag in die Form, die ``_parse`` erwartet."""
        item = entry.get("productItem") or entry
        url = item.get("url") or ""
        if url.startswith("/"):
            url = BASE_URL + url
        photos = item.get("photos") or []
        full_size = photos[0].get("url", "") if photos else ""
        thumb = item.get("thumbnailUrl") or full_size
        return {
            "id": item.get("id", entry.get("id", "")),
            "title": item.get("title", "Unbekannt"),
            "price": item.get("price"),
            "total_item_price": item.get("totalItemPrice"),
            "url": url,
            "user": item.get("user") or {},
            "photo": {"url": thumb, "full_size_url": full_size or thumb} if thumb else None,
            "created_at_ts": item.get("created_at_ts"),
        }

    def _get_catalog(self, params: dict):
        return self.session.get(
            CATALOG_URL,
            params=params,
            headers={"Accept": "text/html,application/xhtml+xml"},
            timeout=20,
        )

    def search(self, term: str, max_results: int = 20) -> List[Listing]:
        logger.info(f"[Vinted] '{term}'")
        params: dict = {
            "search_text": term,
            "order": "newest_first",
        }
        if self.max_price is not None:
            params["price_to"] = self.max_price
        try:
            r = self._get_catalog(params)
            if r.status_code in (401, 403):
                logger.info(f"[Vinted] {r.status_code} – hole neuen Session-Cookie...")
                self._authenticate()
                r = self._get_catalog(params)
            r.raise_for_status()
            items = self._extract_catalog_items(r.text)[:max_results]
        except Exception as e:
            logger.error(f"[Vinted] Fehler bei '{term}': {e}")
            return []

        cutoff_ts = (time.time() - self.max_age_hours * 3600) if self.max_age_hours > 0 else None

        results = []
        for item in items:
            if cutoff_ts is not None:
                created_ts = item.get("created_at_ts")
                if created_ts is not None and float(created_ts) < cutoff_ts:
                    continue
            listing = self._parse(item, term)
            if not listing:
                continue
            if self._home and self.radius_km > 0:
                city = (item.get("user") or {}).get("city", "")
                if city:
                    coords = geocode(city)
                    if coords and haversine(self._home[0], self._home[1], coords[0], coords[1]) > self.radius_km:
                        continue
            results.append(listing)
        logger.info(f"[Vinted] {len(results)} Treffer für '{term}'.")
        return results

    def _parse(self, item: dict, term: str) -> Optional[Listing]:
        try:
            item_id = str(item.get("id", ""))

            raw_price = item.get("price")
            if isinstance(raw_price, dict):
                raw_price = raw_price.get("amount")
            if raw_price is None:
                raw_price = (item.get("total_item_price") or {}).get("amount")
            try:
                price_str = f"{float(raw_price):.2f} €" if raw_price not in (None, "") else "k.A."
            except (ValueError, TypeError):
                price_str = "k.A."

            user = item.get("user") or {}
            location = user.get("city", "")

            photo = item.get("photo") or {}
            image_url = photo.get("url", "")
            image_url_large = photo.get("full_size_url") or image_url

            return Listing(
                platform="Vinted",
                title=item.get("title", "Unbekannt"),
                price=price_str,
                location=location,
                url=item.get("url", f"https://www.vinted.de/items/{item_id}"),
                listing_id=f"vt_{item_id}",
                search_term=term,
                description=item.get("description", ""),
                image_url=image_url,
                image_url_large=image_url_large,
            )
        except Exception as e:
            logger.debug(f"[Vinted] Parse-Fehler: {e}")
            return None
