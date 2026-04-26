"""E-Mail-Benachrichtigung: Sofort-Alerts und Tages-Digest."""

import logging
import smtplib
from collections import defaultdict
from dataclasses import asdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from . import database as db

logger = logging.getLogger(__name__)


# ── Sofort-Benachrichtigung (manueller Crawl) ────────────────

def notify(listings: list, settings: dict, force: bool = False) -> bool:
    """Sendet sofortige E-Mail für manuell gestartete Crawls und markiert Listings als benachrichtigt."""
    if not int(settings.get("email_enabled", 0)):
        return False
    if not listings:
        return False

    listing_dicts = [asdict(l) for l in listings]
    tpl = settings.get("email_subject_alert", "🍼 Baby-Crawler: {n} neue Anzeige(n) gefunden!")
    subject = tpl.replace("{n}", str(len(listing_dicts)))
    result = _send_dicts(subject, listing_dicts, settings)
    if result:
        db.mark_listings_notified([l.listing_id for l in listings])
    return result


# ── Gebündelter Benachrichtigungs-Job (alle 15 Min.) ─────────

def notify_pending(settings: dict) -> bool:
    """Sammelt alle unbenachrichtigten Anzeigen und sendet eine gebündelte E-Mail."""
    if not int(settings.get("email_enabled", 0)):
        return False

    listings = db.get_unnotified_listings()
    if not listings:
        logger.debug("notify_pending: Keine unbenachrichtigten Anzeigen.")
        return False

    tpl = settings.get("email_subject_alert", "🍼 Baby-Crawler: {n} neue Anzeige(n) gefunden!")
    subject = tpl.replace("{n}", str(len(listings)))
    result = _send_dicts(subject, listings, settings)
    if result:
        db.mark_listings_notified([l["listing_id"] for l in listings])
        logger.info(f"notify_pending: {len(listings)} Anzeigen benachrichtigt.")
    return result


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

    tpl = settings.get("email_subject_digest", "🍼 Baby-Crawler Tages-Digest: {n} Anzeige(n) heute")
    subject = tpl.replace("{n}", str(len(listings)))
    logger.info(f"Sende Tages-Digest mit {len(listings)} Anzeigen.")
    return _send_digest_mail(subject, listings, settings)


# ── Interner Versand ─────────────────────────────────────────

def _send_dicts(subject: str, listings: list, settings: dict) -> bool:
    """Sendet eine E-Mail mit gruppierten Listings (als Dicts)."""
    sender, password, recipients = _get_email_config(settings)
    if not recipients:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(_text_from_dicts(listings), "plain", "utf-8"))
    msg.attach(MIMEText(_html_grouped(listings), "html", "utf-8"))

    if _smtp_send(msg, sender, password, recipients, settings):
        logger.info(f"E-Mail '{subject}' → {', '.join(recipients)}")
        return True
    return False


def _send_digest_mail(subject: str, listings: list, settings: dict) -> bool:
    """Sendet eine E-Mail mit Listings als Dicts (aus DB), flaches Format für Digest."""
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
    smtp_port = int(settings.get("email_smtp_port") or 587)
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
    "Vinted": "#e0f2f1",
    "eBay": "#fff8e1",
    "Facebook": "#e8eaf6",
}

_PLATFORM_HEADER_COLORS = {
    "Kleinanzeigen": "#2e7d32",
    "Shpock": "#1565c0",
    "Vinted": "#00695c",
    "eBay": "#e65100",
    "Facebook": "#283593",
}


def _card_html(title, platform, search_term, price, location, url,
               image_url="", is_free=False, distance_km=None,
               found_at="", is_digest=False) -> str:
    bg = "#dcedc8" if is_free else _PLATFORM_COLORS.get(platform, "#f5f5f5")
    img = (f'<img src="{image_url}" style="max-width:180px;border-radius:6px;'
           f'margin-bottom:8px"><br>') if image_url else ""
    free_badge = ('<span style="background:#1b5e20;color:#fff;font-size:11px;'
                  'padding:2px 8px;border-radius:12px;font-weight:bold;'
                  'margin-left:6px">🎁 Gratis</span>') if is_free else ""
    dist_str = (f'<span style="color:#888;font-size:12px;margin-left:6px">'
                f'📍 {distance_km:.0f} km entfernt</span>') if distance_km is not None else ""
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


def _html_grouped(listings: list) -> str:
    """Grupiertes HTML-E-Mail: Plattform → Suchbegriff mit Inhaltsverzeichnis."""
    groups: dict = defaultdict(lambda: defaultdict(list))
    for l in listings:
        groups[l.get("platform", "Unbekannt")][l.get("search_term", "")].append(l)

    # Inhaltsverzeichnis
    toc_rows = []
    for platform in sorted(groups):
        total = sum(len(v) for v in groups[platform].values())
        hc = _PLATFORM_HEADER_COLORS.get(platform, "#333")
        toc_rows.append(
            f'<tr><td style="padding:3px 8px;font-weight:bold;color:{hc}">{platform}</td>'
            f'<td style="padding:3px 8px;color:#666">{total} Anzeige(n)</td></tr>'
        )
        for term in sorted(groups[platform]):
            count = len(groups[platform][term])
            toc_rows.append(
                f'<tr><td style="padding:1px 8px 1px 20px;color:#777">↳ {term}</td>'
                f'<td style="padding:1px 8px;color:#999">{count}</td></tr>'
            )
    toc = f'<table style="border-collapse:collapse">{"".join(toc_rows)}</table>'

    # Sektionen
    sections = []
    for platform in sorted(groups):
        bg = _PLATFORM_COLORS.get(platform, "#f5f5f5")
        hc = _PLATFORM_HEADER_COLORS.get(platform, "#333")
        sections.append(
            f'<div style="margin-top:28px">'
            f'<div style="background:{bg};border-left:5px solid {hc};'
            f'padding:10px 14px;border-radius:0 6px 6px 0;margin-bottom:12px">'
            f'<h3 style="margin:0;color:{hc};font-size:16px">{platform}</h3>'
            f'</div>'
        )
        for term in sorted(groups[platform]):
            items = groups[platform][term]
            cards = "".join(
                _card_html(
                    title=l.get("title", ""), platform=platform, search_term=term,
                    price=l.get("price", ""), location=l.get("location", ""),
                    url=l.get("url", ""), image_url=l.get("image_url", ""),
                    is_free=bool(l.get("is_free")), distance_km=l.get("distance_km"),
                    found_at=l.get("found_at", ""),
                )
                for l in items
            )
            sections.append(
                f'<div style="margin-left:12px;margin-bottom:16px">'
                f'<h4 style="margin:0 0 8px;color:#555;border-bottom:1px solid #ddd;'
                f'padding-bottom:4px;font-size:13px">🔍 {term} ({len(items)})</h4>'
                f'{cards}</div>'
            )
        sections.append('</div>')

    count = len(listings)
    return (
        '<html><body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;padding:20px">'
        f'<h2 style="color:#333">🍼 {count} neue Babysachen</h2>'
        '<div style="background:#f9f9f9;border:1px solid #eee;border-radius:8px;'
        'padding:14px;margin-bottom:24px">'
        '<p style="margin:0 0 8px;font-weight:bold;color:#333">Inhalt</p>'
        f'{toc}</div>'
        + "".join(sections)
        + '<p style="color:#aaa;font-size:11px;margin-top:24px">'
        'Baby-Crawler – automatische Benachrichtigung</p>'
        '</body></html>'
    )


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
    heading = f"{'Tages-Digest: ' if is_digest else ''}{count} Babysachen"
    footer = "Tages-Zusammenfassung" if is_digest else "automatische Benachrichtigung"
    return f"""<html><body style="font-family:Arial,sans-serif;max-width:680px;
      margin:0 auto;padding:20px">
      <h2 style="color:#333">🍼 {heading}</h2>{cards}
      <p style="color:#aaa;font-size:11px">Baby-Crawler – {footer}</p>
    </body></html>"""


def _text_from_dicts(listings: list, is_digest: bool = False) -> str:
    heading = f"Baby-Crawler {'Tages-Digest' if is_digest else 'Benachrichtigung'}: {len(listings)} Anzeige(n)"
    lines = [heading + "\n" + "=" * 50]
    for l in listings:
        free = " [GRATIS]" if l.get("is_free") else ""
        dist = f" ({l['distance_km']:.0f} km)" if l.get("distance_km") is not None else ""
        lines += [
            f"\n[{l.get('platform')}] {l.get('title')}{free}",
            f"Preis: {l.get('price')}{dist}",
            f"Ort:   {l.get('location')}",
            f"Link:  {l.get('url')}",
            "-" * 50,
        ]
    return "\n".join(lines)
