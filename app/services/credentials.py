"""Rotating QR token (10 s) and 4-digit code (5 s), derived statelessly from one secret (D30, D31).

Nothing is stored: a value is an HMAC of the session id and the time slice, so the server only
needs the key and the injected clock to create and check it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

from app.clock import Clock
from app.errors import QrExpiredError

_SIG_LEN = 16  # bytes of truncated HMAC-SHA256 kept in the QR token


class RotatingCredentials:
    """Creates and verifies the projector QR token and the short code shown under it."""

    QR_PERIOD_S = 10
    QR_MAX_AGE_S = 15
    CODE_PERIOD_S = 5
    # 4 digits: a random guess hits the current or previous code with probability 2 / 10,000 (D33).
    CODE_DIGITS = 4

    def __init__(self, secret_key: str, clock: Clock) -> None:
        self._key = secret_key.encode()
        self._clock = clock

    def _mac(self, domain: bytes, message: bytes) -> bytes:
        # The domain prefix keeps QR signatures and codes independent although they share one key.
        return hmac.new(self._key, domain + b":" + message, hashlib.sha256).digest()

    def qr_token(self, session_id: int) -> str:
        """Token for the current 10 s slice; its creation time is the start of that slice (D31)."""
        created = int(self._clock.now()) // self.QR_PERIOD_S * self.QR_PERIOD_S
        msg = f"{session_id}|{created}".encode()
        raw = msg + b"|" + self._mac(b"qr", msg)[:_SIG_LEN]
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def verify_qr(self, token: str) -> int:
        """Return the session id of a genuine token at most 15 s old, else raise QrExpiredError."""
        try:
            raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
            # The signature is binary and may contain b"|": cut it by its fixed length, not by separator.
            msg, sig = raw[: -_SIG_LEN - 1], raw[-_SIG_LEN:]
            session_part, created_part = msg.decode().split("|")
            session_id, created = int(session_part), int(created_part)
        except ValueError as exc:  # also covers bad base64 and bad UTF-8 (both ValueError subclasses)
            raise QrExpiredError() from exc
        genuine = hmac.compare_digest(sig, self._mac(b"qr", msg)[:_SIG_LEN])
        age = self._clock.now() - created
        if not genuine or not 0 <= age <= self.QR_MAX_AGE_S:
            raise QrExpiredError()
        return session_id

    def _code_for_slice(self, session_id: int, slice_no: int) -> str:
        digest = self._mac(b"code", f"{session_id}|{slice_no}".encode())
        return f"{int.from_bytes(digest[:8], 'big') % 10000:04d}"

    def current_code(self, session_id: int) -> str:
        """The 4-digit code (zero-padded, e.g. 0042) of the current 5 s slice."""
        return self._code_for_slice(session_id, int(self._clock.now()) // self.CODE_PERIOD_S)

    def is_valid_code(self, session_id: int, code: str) -> bool:
        """True for the current or the immediately previous slice's code (P1); never raises."""
        if not isinstance(code, str) or len(code) != self.CODE_DIGITS or not (code.isascii() and code.isdigit()):
            return False
        slice_no = int(self._clock.now()) // self.CODE_PERIOD_S
        return any(
            hmac.compare_digest(code, self._code_for_slice(session_id, n))
            for n in (slice_no, slice_no - 1)
        )
