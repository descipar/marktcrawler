"""Routen-Package: Blueprint-Registrierung."""

from flask import Blueprint

bp = Blueprint("main", __name__)

from . import views, api, profiles  # noqa: E402 – Routen auf bp registrieren
