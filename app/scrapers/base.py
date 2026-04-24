"""Gemeinsame Datenstruktur für alle Scraper."""
from dataclasses import dataclass, field


@dataclass
class Listing:
    platform: str
    title: str
    price: str
    location: str
    url: str
    listing_id: str
    search_term: str = ""
    description: str = ""
    image_url: str = ""
    is_free: bool = False
    distance_km: float = None
