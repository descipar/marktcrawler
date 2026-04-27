"""E-Mail-Benachrichtigung: Sofort-Alerts und Tages-Digest."""

import logging
import os
import smtplib
import socket
from collections import defaultdict
from dataclasses import asdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import List

from . import database as db

logger = logging.getLogger(__name__)


# ── Sofort-Benachrichtigung (manueller Crawl) ────────────────

def notify(listings: list, settings: dict, force: bool = False) -> bool:
    """Sendet sofortige E-Mail für manuell gestartete Crawls und markiert Listings als benachrichtigt."""
    if not int(settings.get("email_enabled") or 0):
        return False
    if not listings:
        return False

    listing_dicts = [asdict(l) for l in listings]
    tpl = settings.get("email_subject_alert", "🔍 Marktcrawler: {n} neue Anzeige(n) gefunden!")
    subject = tpl.replace("{n}", str(len(listing_dicts)))
    result = _send_dicts(subject, listing_dicts, settings)
    if result:
        db.mark_listings_notified([l.listing_id for l in listings])
        raw_r = os.environ.get("EMAIL_RECIPIENT") or settings.get("email_recipient", "")
        db.log_notification("alert", len(listing_dicts),
                            len([r for r in raw_r.split(",") if r.strip()]))
    return result


# ── Gebündelter Benachrichtigungs-Job (alle 15 Min.) ─────────

def notify_pending(settings: dict) -> bool:
    """Sammelt alle unbenachrichtigten Anzeigen und sendet eine gebündelte E-Mail.

    B5-Fix: claim_unnotified_listings() holt und markiert atomar in einer
    Transaktion, sodass bei gleichzeitigen Aufrufen keine doppelten E-Mails
    entstehen können.
    """
    if not int(settings.get("email_enabled") or 0):
        return False

    listings = db.claim_unnotified_listings()
    if not listings:
        logger.debug("notify_pending: Keine unbenachrichtigten Anzeigen.")
        return False

    tpl = settings.get("email_subject_alert", "🔍 Marktcrawler: {n} neue Anzeige(n) gefunden!")
    subject = tpl.replace("{n}", str(len(listings)))
    result = _send_dicts(subject, listings, settings)
    if result:
        logger.info(f"notify_pending: {len(listings)} Anzeigen benachrichtigt.")
        raw_r = os.environ.get("EMAIL_RECIPIENT") or settings.get("email_recipient", "")
        db.log_notification("alert", len(listings),
                            len([r for r in raw_r.split(",") if r.strip()]))
    return result


# ── Tages-Digest ─────────────────────────────────────────────

def send_digest(settings: dict) -> bool:
    """Sendet die tägliche Zusammenfassung aller heute gefundenen Anzeigen."""
    if not int(settings.get("digest_enabled") or 0):
        return False
    if not int(settings.get("email_enabled") or 0):
        return False

    listings = db.get_listings_today()
    if not listings:
        logger.info("Digest: Heute keine Anzeigen gefunden – kein Versand.")
        return False

    tpl = settings.get("email_subject_digest", "🔍 Marktcrawler Tages-Digest: {n} Anzeige(n) heute")
    subject = tpl.replace("{n}", str(len(listings)))
    logger.info(f"Sende Tages-Digest mit {len(listings)} Anzeigen.")
    result = _send_dicts(subject, listings, settings, is_digest=True)
    if result:
        raw_r = os.environ.get("EMAIL_RECIPIENT") or settings.get("email_recipient", "")
        db.log_notification("digest", len(listings),
                            len([r for r in raw_r.split(",") if r.strip()]))
    return result


# ── Interner Versand ─────────────────────────────────────────

def _send_dicts(subject: str, listings: list, settings: dict, is_digest: bool = False) -> bool:
    """Sendet eine E-Mail mit gruppierten Listings (als Dicts)."""
    sender, password, recipients = _get_email_config(settings)
    if not recipients:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(_text_from_dicts(listings, is_digest=is_digest), "plain", "utf-8"))
    msg.attach(MIMEText(_html_email(listings, is_digest=is_digest, settings=settings), "html", "utf-8"))

    if _smtp_send(msg, sender, password, recipients, settings):
        logger.info(f"E-Mail '{subject}' → {', '.join(recipients)}")
        return True
    return False


def _get_email_config(settings: dict):
    """Liest E-Mail-Konfiguration – Env-Variablen haben Vorrang vor DB-Settings."""
    sender = os.environ.get("EMAIL_SENDER") or settings.get("email_sender", "")
    password = os.environ.get("EMAIL_PASSWORD") or settings.get("email_password", "")
    raw = os.environ.get("EMAIL_RECIPIENT") or settings.get("email_recipient", "")
    if not all([sender, password, raw]):
        logger.warning("E-Mail-Konfiguration unvollständig – kein Versand.")
        return sender, password, []
    recipients = [r.strip() for r in raw.split(",") if r.strip()]
    return sender, password, recipients


def _smtp_send(msg, sender: str, password: str, recipients: list, settings: dict) -> bool:
    smtp_server = os.environ.get("EMAIL_SMTP_SERVER") or settings.get("email_smtp_server", "smtp.gmail.com")
    smtp_port = int(os.environ.get("EMAIL_SMTP_PORT") or settings.get("email_smtp_port") or 587)
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
               found_at="", is_digest=False, db_id=None, server_url="") -> str:
    bg = "#dcedc8" if is_free else _PLATFORM_COLORS.get(platform, "#f5f5f5")
    img = (f'<img src="{escape(image_url)}" style="max-width:180px;border-radius:6px;'
           f'margin-bottom:8px"><br>') if image_url else ""
    free_badge = ('<span style="background:#1b5e20;color:#fff;font-size:11px;'
                  'padding:2px 8px;border-radius:12px;font-weight:bold;'
                  'margin-left:6px">🎁 Gratis</span>') if is_free else ""
    dist_str = (f'<span style="color:#888;font-size:12px;margin-left:6px">'
                f'📍 {distance_km:.0f} km entfernt</span>') if distance_km is not None else ""
    date_str = (f'<div style="color:#aaa;font-size:11px;margin-top:4px">'
                f'{escape(found_at).replace("T"," ")}</div>') if is_digest else ""
    dashboard_btn = (
        f'<a href="{escape(server_url)}/?modal={db_id}" '
        f'style="padding:6px 14px;background:#388e3c;color:white;'
        f'text-decoration:none;border-radius:4px;font-size:13px;margin-left:6px">'
        f'Im Dashboard →</a>'
    ) if (server_url and db_id) else ""

    return f"""
    <div style="background:{bg};border:1px solid #ddd;border-radius:8px;
                padding:14px;margin-bottom:12px">
      <div style="font-size:11px;color:#888;margin-bottom:4px">
        {escape(platform)} · {escape(search_term)}
      </div>
      <div style="font-weight:bold;font-size:15px;color:#333;margin-bottom:6px">
        {escape(title)}
      </div>
      {img}
      <div style="margin-bottom:6px">
        <span style="font-size:18px;font-weight:bold;color:#2e7d32">{escape(price)}</span>
        {free_badge}
        {dist_str}
      </div>
      <div style="color:#555;font-size:13px;margin-bottom:8px">📍 {escape(location)}</div>
      {date_str}
      <a href="{escape(url)}" style="padding:6px 14px;background:#1976d2;color:white;
         text-decoration:none;border-radius:4px;font-size:13px">Ansehen →</a>
      {dashboard_btn}
    </div>"""


def _normalize_server_url(raw: str) -> str:
    """Ergänzt fehlendes Schema und Port, damit reine IPs/Hostnamen funktionieren."""
    if not raw:
        return ""
    # Schema ergänzen
    if not raw.startswith(("http://", "https://")):
        raw = "http://" + raw
    # Port ergänzen wenn keiner vorhanden (kein ":" nach dem Host-Teil)
    from urllib.parse import urlparse
    parsed = urlparse(raw)
    if not parsed.port:
        raw = raw.rstrip("/") + ":5000"
    return raw.rstrip("/")


def _get_server_url(settings: dict) -> str:
    """Gibt die konfigurierte oder automatisch erkannte Server-URL zurück."""
    url = settings.get("server_url", "").strip()
    if url:
        return _normalize_server_url(url)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return f"http://{ip}:5000"
    except Exception:
        return ""


def _html_email(listings: list, is_digest: bool = False, settings: dict | None = None) -> str:
    """Vereinheitlichter HTML-Builder: gruppiert nach Plattform → Suchbegriff."""
    srv = _get_server_url(settings or {})
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
                    found_at=l.get("found_at", ""), is_digest=is_digest,
                    db_id=l.get("id"), server_url=srv,
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
    if is_digest:
        heading = f"Tages-Digest: {count} Babysachen"
        footer = "Tages-Zusammenfassung"
    else:
        heading = f"{count} neue Babysachen"
        footer = "automatische Benachrichtigung"

    dashboard_btn = (
        f'<p style="margin-top:20px">'
        f'<a href="{escape(srv)}" '
        f'style="background:#7c3aed;color:#fff;padding:10px 20px;border-radius:6px;'
        f'text-decoration:none;font-size:14px;font-weight:bold">🔍 Zum Dashboard →</a></p>'
    ) if srv else ""

    return (
        '<html><body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;padding:20px">'
        f'<h2 style="color:#333">🔍 {heading}</h2>'
        '<div style="background:#f9f9f9;border:1px solid #eee;border-radius:8px;'
        'padding:14px;margin-bottom:24px">'
        '<p style="margin:0 0 8px;font-weight:bold;color:#333">Inhalt</p>'
        f'{toc}'
        f'{dashboard_btn}'
        f'</div>'
        + "".join(sections)
        + f'<p style="color:#aaa;font-size:11px;margin-top:24px">Marktcrawler – {footer}</p>'
        '</body></html>'
    )


# Backward-compat-Aliases für Tests und Digest
def _html_grouped(listings: list) -> str:
    return _html_email(listings)


def _html_from_dicts(listings: list, is_digest: bool = False) -> str:
    return _html_email(listings, is_digest=is_digest)


def _text_from_dicts(listings: list, is_digest: bool = False) -> str:
    heading = f"Marktcrawler {'Tages-Digest' if is_digest else 'Benachrichtigung'}: {len(listings)} Anzeige(n)"
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
