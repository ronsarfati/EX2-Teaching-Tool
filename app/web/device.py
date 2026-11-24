"""Per-request helpers: the anonymous, server-signed device token (FR-1.7, D6, D31, D37).

The token is random and linked to no person (D5, D6). Since D37 it is signed with an HMAC so a
client cannot invent one, and the phone mirrors it in three places (cookie, localStorage,
IndexedDB, see static/device.js). If the cookie was deleted but a valid mirrored copy comes back,
that older copy is the identity again, so deleting cookies no longer gives a second check-in.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from typing import Optional

from flask import Response, current_app, g, request

COOKIE_NAME = "dt"
STORED_FIELD = "dt_stored"  # hidden form field carrying the localStorage / IndexedDB copy
ONE_YEAR_SECONDS = 365 * 24 * 3600
_SIGNATURE_BYTES = 16
# Tokens issued before D37 were bare random strings (no "."): still accepted as cookies.
_LEGACY_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def _signature(raw: str) -> str:
    key = current_app.config["SECRET_KEY"].encode()
    digest = hmac.new(key, raw.encode(), hashlib.sha256).digest()[:_SIGNATURE_BYTES]
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def sign(raw: str) -> str:
    """Return the value stored on the phone: `<random>.<signature>`."""
    return f"{raw}.{_signature(raw)}"


def verify_signed(value: Optional[str]) -> Optional[str]:
    """Return the random part of a correctly signed token, else None (forged or malformed)."""
    if not value or value.count(".") != 1:
        return None
    raw, signature = value.split(".")
    if not _LEGACY_TOKEN.match(raw):
        return None
    return raw if hmac.compare_digest(signature, _signature(raw)) else None


def _cookie_identity() -> Optional[str]:
    """The identity in the cookie: signed, or a legacy bare token; None if absent or forged."""
    value = request.cookies.get(COOKIE_NAME)
    if not value:
        return None
    if "." in value:
        return verify_signed(value)
    return value if _LEGACY_TOKEN.match(value) else None


def stored_identity(candidates: list[str]) -> Optional[str]:
    """First validly signed mirrored copy among the candidates (forged ones are ignored)."""
    for value in candidates:
        raw = verify_signed(value)
        if raw:
            return raw
    return None


def _mirrored_candidates() -> list[str]:
    hint = g.get("stored_hint") or []
    return [*hint, request.form.get(STORED_FIELD, "")] if request.method == "POST" else list(hint)


def device_token() -> str:
    """Return this phone's identity: the older mirrored copy if valid, else the cookie, else a new one."""
    if "device_identity" not in g:
        stored = stored_identity(_mirrored_candidates())
        g.device_identity = stored or _cookie_identity() or secrets.token_urlsafe(16)
    return g.device_identity


def cookie_differs_from_stored(candidates: list[str]) -> bool:
    """True when a valid mirrored copy exists and is not the identity the cookie carries."""
    stored = stored_identity(candidates)
    return stored is not None and stored != _cookie_identity()


def signed_current_token() -> str:
    """The signed form of the current identity, for the browser to mirror."""
    return sign(device_token())


def attach_device_cookie(response: Response) -> Response:
    """(Re)set the signed cookie when it is missing, legacy or different. Server-set: Safari keeps it a year."""
    if "device_identity" not in g:
        return response
    wanted = sign(g.device_identity)
    if request.cookies.get(COOKIE_NAME) != wanted:
        response.set_cookie(COOKIE_NAME, wanted, max_age=ONE_YEAR_SECONDS, httponly=True, samesite="Lax")
    return response
