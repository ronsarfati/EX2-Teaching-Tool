"""Per-request helpers: the anonymous device token (FR-1.7, D6, D31) and the client address (FR-1.2)."""
from __future__ import annotations

import secrets

from flask import Response, g, request

from app.services.network import NetworkPolicy

COOKIE_NAME = "dt"
ONE_YEAR_SECONDS = 365 * 24 * 3600


def device_token() -> str:
    """Return the browser's random token, creating it if absent.

    A new token is parked on `g` so `attach_device_cookie` can send it after the view ran.
    The token is random and linked to no person (D6): it only recognises a returning phone.
    """
    existing = request.cookies.get(COOKIE_NAME)
    if existing:
        return existing
    if "new_device_token" not in g:
        g.new_device_token = secrets.token_urlsafe(16)
    return g.new_device_token


def attach_device_cookie(response: Response) -> Response:
    """Set the cookie created during this request. Server-set, so Safari keeps it a full year."""
    token = g.get("new_device_token")
    if token:
        response.set_cookie(
            COOKIE_NAME, token, max_age=ONE_YEAR_SECONDS, httponly=True, samesite="Lax"
        )
    return response


def client_ip() -> str:
    """Campus-filter address: the socket peer, or CF-Connecting-IP when the peer is the local tunnel."""
    return NetworkPolicy.resolve_client_ip(
        request.remote_addr or "", request.headers.get("CF-Connecting-IP")
    )
