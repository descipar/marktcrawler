"""E-Mail-Benachrichtigung: Sofort-Alerts und Tages-Digest."""

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from . import database as db

logger = logging.getLogger(__name__)

_last_sent: float = 0.0


# ── Sofort-Benachrichtigung ──────────────────────────────────

def notify(listings: list, settings: dict) -> bool:
    """Sendet sofortige E-Mail bei neuen Anzeigen."""
    global _last_sent
    if not int(settings.get("email_enabled", 0)):
        return False
    if not listings:
        return False

    min_interval = int(settings.get("crawler_interval", 60)) * 60
    if time.time() - _last_sent < min_interval:
        return False

    subject = f"🍼 Baby-Crawler: {len(listings)} neue Anzeige(n) gefunden!"
    return _send(subject, listings, settings)


# ── Tages-Digest ─────────────────────────────────────────────

def send_digest(settings: dict) -> bool:
    """Sendet die tägliche Zusammenfassung aller heute gefundenen Anzeigen."""
    if not int(settings.get("digest_enabled", 0)):
        return False
    if not int(settings.get("email_enabled", 0)):
        return False

    listings = db.get_listings_today()
    if not listings:
        logger.info("Digest: Heute keine Anzeigen gefunden – kein Versand.")
        return False

    # listings sind hier Dicts aus der DB, keine Listing-Objekte
    subject = f"🍼 Baby-Crawler Tages-Digest: {len(listings)} Anzeige(n) heute"
    logger.info(f"Sende Tages-Digest mit {len(listings)} Anzeigen.")
    return _send_digest_mail(subject, listings, settings)


# ── Interner Versand ─────────────────────────────────────────

def _send(subject: str, listings: list, settings: dict) -> bool:
    """Sendet eine E-Mail mit Listing-Objekten."""
    sender, password, recipients = _get_email_config(settings)
    if not recipients:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(_text_from_objects(listings), "plain", "utf-8"))
    msg.attach(MIMEText(_html_from_objects(listings), "html", "utf-8"))

    if _smtp_send(msg, sender, password, recipients, settings):
        global _last_sent
        _last_sent = time.time()
        logger.info(f"E-Mail '{subject}' → {', '.join(recipients)}")
        return True
    return False


def _send_digest_mail(subject: str, listings: list, settings: dict) -> bool:
    """Sendet eine E-Mail mit Listings als Dicts (aus DB)."""
    sender, password, recipients = _get_email_config(settings)
    if not recipients:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(_text_from_dicts(listings), "plain", "utf-8"))
    msg.attach(MIMEText(_html_from_dicts(listings, is_digest=True), "html", "utf-8"))

    return _smtp_send(msg, sender, password, recipients, settings)


def _get_email_config(settings: dict):
    sender = settings.get("email_sender", "")
    password = settings.get("email_password", "")
    raw = settings.get("email_recipient", "")
    if not all([sender, password, raw]):
        logger.warning("E-Mail-Konfiguration unvollständig – kein Versand.")
        return sender, password, []
    recipients = [r.strip() for r in raw.split(",") if r.strip()]
    return sender, password, recipients


def _smtp_send(msg, sender: str, password: str, recipients: list, settings: dict) -> bool:
    smtp_server = settings.get("email_smtp_server", "smtp.gmail.com")
    smtp_port = int(settings.get("email_smtp_port", 587))
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(sender, password)
            srv.sendmail(sender, recipients, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP-Login fehlgeschlagen. Gmail: App-Passwort verwenden!")
    except Exception as e:
        logger.error(f"E-Mail-Fehler: {e}")
    return False


# ── HTML/Text-Builder ────────────────────────────────────────

_PLATFORM_COLORS = {
    "Kleinanzeigen": "#e8f5e9",
    "Shpock": "#e3f2fd",
    "Facebook": "#e8eaf6",
}


def _card_html(title, platform, search_term, price, location, url,
               image_url="", is_free=False, distance_km=None,
               found_at="", is_digest=False) -> str:
    bg = _PLATFORM_COLORS.get(platform, "#f5f5f5")
    img = (f'<img src="{image_url}" style="max-width:180px;border-radius:6px;'
           f'margin-bottom:8px"><br>') if image_url else ""
    free_badge = ('<span style="background:#e8f5e9;color:#1b5e20;font-size:11px;'
                  'padding:2px 8px;border-radius:12px;font-weight:bold;'
                  'margin-left:6px">🎁 Gratis</span>') if is_free else ""
    dist_str = (f'<span style="color:#888;font-size:12px;margin-left:6px">'
                f'📍 {distance_km:.0f} km entfernt</span>') if distance_km else ""
    date_str = (f'<div style="color:#aaa;font-size:11px;margin-top:4px">'
                f'{found_at.replace("T"," ")}</div>') if is_digest else ""

    return f"""
    <div style="background:{bg};border:1px solid #ddd;border-radius:8px;
                padding:14px;margin-bottom:12px">
      <div style="font-size:11px;color:#888;margin-bottom:4px">
        {platform} · {search_term}
      </div>
      <div style="font-weight:bold;font-size:15px;color:#333;margin-bottom:6px">
        {title}
      </div>
      {img}
      <div style="margin-bottom:6px">
        <span style="font-size:18px;font-weight:bold;color:#2e7d32">{price}</span>
        {free_badge}
        {dist_str}
      </div>
      <div style="color:#555;font-size:13px;margin-bottom:8px">📍 {location}</div>
      {date_str}
      <a href="{url}" style="padding:6px 14px;background:#1976d2;color:white;
         text-decoration:none;border-radius:4px;font-size:13px">Ansehen →</a>
    </div>"""


def _html_from_objects(listings: list, is_digest: bool = False) -> str:
    cards = "".join(
        _card_html(
            title=l.title, platform=l.platform, search_term=l.search_term,
            price=l.price, location=l.location, url=l.url,
            image_url=getattr(l, "image_url", ""),
            is_free=getattr(l, "is_free", False),
            distance_km=getattr(l, "distance_km", None),
            is_digest=is_digest,
        )
        for l in listings
    )
    count = len(listings)
    heading = f"{'Tages-Digest: ' if is_digest else ''}{count} Babysachen"
    return f"""<html><body style="font-family:Arial,sans-serif;max-width:680px;
      margin:0 auto;padding:20px">
      <h2 style="color:#333">🍼 {heading}</h2>{cards}
      <p style="color:#aaa;font-size:11px">Baby-Crawler – automatische Benachrichtigung</p>
    </body></html>"""


def _html_from_dicts(listings: list, is_digest: bool = False) -> str:
    cards = "".join(
        _card_html(
            title=l.get("title", ""), platform=l.get("platform", ""),
            search_term=l.get("search_term", ""), price=l.get("price", ""),
            location=l.get("location", ""), url=l.get("url", ""),
            image_url=l.get("image_url", ""),
            is_free=bool(l.get("is_free")),
            distance_km=l.get("distance_km"),
            found_at=l.get("found_at", ""),
            is_digest=is_digest,
        )
        for l in listings
    )
    count = len(listings)
    return f"""<html><body style="font-family:Arial,sans-serif;max-width:680px;
      margin:0 auto;padding:20px">
      <h2 style="color:#333">🍼 Tages-Digest: {count} Anzeigen heute</h2>{cards}
      <p style="color:#aaa;font-size:11px">Baby-Crawler – Tages-Zusammenfassung</p>
    </body></html>"""


def _text_from_objects(listings: list) -> str:
    lines = [f"Baby-Crawler: {len(listings)} neue Anzeige(n)\n" + "=" * 50]
    for l in listings:
        free = " [GRATIS]" if getattr(l, "is_free", False) else ""
        dist = f" ({l.distance_km:.0f} km)" if getattr(l, "distance_km", None) else ""
        lines += [
            f"\n[{l.platform}] {l.title}{free}",
            f"Preis: {l.price}{dist}",
            f"Ort:   {l.location}",
            f"Link:  {l.url}",
            "-" * 50,
        ]
    return "\n".join(lines)


def _text_from_dicts(listings: list) -> str:
    lines = [f"Baby-Crawler Tages-Digest: {len(listings)} Anzeige(n)\n" + "=" * 50]
    for l in listings:
        free = " [GRATIS]" if l.get("is_free") else ""
        lines += [
            f"\n[{l.get('platform')}] {l.get('title')}{free}",
            f"Preis: {l.get('price')}",
            f"Ort:   {l.get('location')}",
            f"Link:  {l.get('url')}",
            "-" * 50,
        ]
    return "\n".join(lines)
