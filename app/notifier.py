"""E-Mail-Benachrichtigung für neue Anzeigen."""

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

logger = logging.getLogger(__name__)

_last_sent: float = 0.0


def notify(listings: list, settings: dict) -> bool:
    global _last_sent
    if not int(settings.get("email_enabled", 0)):
        return False
    if not listings:
        return False

    min_interval = int(settings.get("crawler_interval", 60)) * 60
    if time.time() - _last_sent < min_interval:
        return False

    sender = settings.get("email_sender", "")
    password = settings.get("email_password", "")
    recipient = settings.get("email_recipient", "")
    if not all([sender, password, recipient]):
        logger.warning("E-Mail-Konfiguration unvollständig – kein Versand.")
        return False

    smtp_server = settings.get("email_smtp_server", "smtp.gmail.com")
    smtp_port = int(settings.get("email_smtp_port", 587))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🍼 Baby-Crawler: {len(listings)} neue Anzeige(n)!"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(_text(listings), "plain", "utf-8"))
    msg.attach(MIMEText(_html(listings), "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(sender, password)
            srv.sendmail(sender, recipient, msg.as_string())
        _last_sent = time.time()
        logger.info(f"E-Mail mit {len(listings)} Anzeigen gesendet an {recipient}.")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP-Login fehlgeschlagen. Gmail: App-Passwort verwenden!")
    except Exception as e:
        logger.error(f"E-Mail-Fehler: {e}")
    return False


def _html(listings: list) -> str:
    COLORS = {"Kleinanzeigen": "#e8f5e9", "Shpock": "#e3f2fd", "Facebook": "#e8eaf6"}
    cards = ""
    for l in listings:
        bg = COLORS.get(l.platform, "#f5f5f5")
        img = f'<img src="{l.image_url}" style="max-width:180px;border-radius:6px;margin-bottom:8px"><br>' if l.image_url else ""
        cards += f"""
        <div style="background:{bg};border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:12px">
          <div style="font-size:11px;color:#888">{l.platform} · {l.search_term}</div>
          <h3 style="margin:4px 0;color:#333">{l.title}</h3>
          {img}
          <div style="font-size:18px;font-weight:bold;color:#2e7d32;margin:6px 0">{l.price}</div>
          <div style="color:#555;margin-bottom:8px">📍 {l.location}</div>
          <a href="{l.url}" style="padding:7px 14px;background:#1976d2;color:white;text-decoration:none;border-radius:4px">Ansehen</a>
        </div>"""
    return f"""<html><body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;padding:20px">
      <h2 style="color:#333">🍼 {len(listings)} neue Babysachen!</h2>{cards}
      <p style="color:#aaa;font-size:11px">Baby-Crawler – automatische Benachrichtigung</p>
    </body></html>"""


def _text(listings: list) -> str:
    lines = [f"Baby-Crawler: {len(listings)} neue Anzeige(n)\n" + "="*50]
    for l in listings:
        lines += [f"\n[{l.platform}] {l.title}", f"Preis: {l.price}", f"Ort:   {l.location}", f"Link:  {l.url}", "-"*50]
    return "\n".join(lines)
