"""Check-in rules (FR-1.2, FR-1.6-FR-1.12, D30, D31): the order of the checks is the design (SD-2)."""
from __future__ import annotations

from typing import Optional

from app.clock import Clock
from app.db import Database
from app.errors import (
    AlreadyCheckedInError,
    CheckInError,
    EmptyNicknameError,
    SessionClosedError,
    TooManyAttemptsError,
    WindowExpiredError,
    WrongCodeError,
)
from app.repositories.checkins import CheckIn, CheckInRepository, NetworkOrigin
from app.repositories.sessions import SessionRepository
from app.repositories.windows import CheckInWindowRepository
from app.services.credentials import RotatingCredentials
from app.services.network import NetworkPolicy
from app.services.text import strip_invisible


class CheckInService:
    WINDOW_SECONDS = 60
    MAX_ATTEMPTS = 5
    NICKNAME_MAX_LEN = 30

    def __init__(
        self,
        network: NetworkPolicy,
        credentials: RotatingCredentials,
        sessions: SessionRepository,
        check_ins: CheckInRepository,
        windows: CheckInWindowRepository,
        db: Database,
        clock: Clock,
    ) -> None:
        self._network = network
        self._credentials = credentials
        self._sessions = sessions
        self._check_ins = check_ins
        self._windows = windows
        self._db = db
        self._clock = clock

    def start(self, qr_token: str, device_token: str, client_ip: str) -> Optional[str]:
        """Handle a QR scan: open a fresh 1-minute window; return the stored nickname or None (first visit)."""
        self._network.ensure_allowed(client_ip)
        session_id = self._credentials.verify_qr(qr_token)
        with self._db.transaction():
            session = self._sessions.get(session_id)
            if session is None or not session.is_open():
                raise SessionClosedError()
            if self._check_ins.has_checked_in(session_id, device_token):
                raise AlreadyCheckedInError()
            # A new scan replaces any previous window, so attempts restart at 0 (FR-1.9).
            self._windows.open(session_id, device_token, self._clock.now())
            return self._check_ins.nickname_of(device_token)

    def confirm(self, device_token: str, client_ip: str, code: str, nickname: Optional[str]) -> CheckIn:
        """Validate the typed code (and the nickname on a first visit) and record the check-in."""
        origin = self._network.classify(client_ip)  # the origin of the confirm request is the one stored
        # A raise inside the transaction rolls it back, which would also undo the attempt counter.
        # So the refusals that must persist are returned, and raised only after the commit.
        with self._db.transaction():
            outcome = self._confirm_in_transaction(device_token, code, nickname, origin)
        if isinstance(outcome, CheckInError):
            raise outcome
        return outcome

    def _confirm_in_transaction(
        self, device_token: str, code: str, nickname: Optional[str], origin: NetworkOrigin
    ) -> CheckIn | CheckInError:
        now = self._clock.now()
        window = self._windows.find(device_token)
        if window is None or now - window.opened_at > self.WINDOW_SECONDS:
            return WindowExpiredError()
        session_id = window.session_id
        session = self._sessions.get(session_id)
        if session is None or not session.is_open():
            return SessionClosedError()
        stored = self._check_ins.nickname_of(device_token)
        chosen = stored if stored is not None else strip_invisible(nickname or "").strip()
        if not 1 <= len(chosen) <= self.NICKNAME_MAX_LEN:
            return EmptyNicknameError()  # not counted as an attempt (D31)
        if self._windows.increment_attempts(session_id, device_token) > self.MAX_ATTEMPTS:
            self._windows.delete(session_id, device_token)
            return TooManyAttemptsError()
        if not self._credentials.is_valid_code(session_id, code):
            return WrongCodeError()
        if stored is None:
            self._check_ins.save_nickname(device_token, chosen, now)
        check_in = self._check_ins.add(session_id, device_token, chosen, now, origin)
        self._windows.delete(session_id, device_token)
        return check_in
