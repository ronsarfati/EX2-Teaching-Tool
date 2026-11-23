"""Lifecycle of the single attendance session (FR-1.1, FR-1.13, D27)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.clock import Clock
from app.errors import SessionAlreadyOpenError
from app.repositories.sessions import AttendanceSession, SessionRepository
from app.services.credentials import RotatingCredentials


@dataclass(frozen=True)
class ProjectorState:
    """What the projector shows: the URL to encode in the QR and the 3-digit code."""

    check_in_url: str
    code: str


class SessionService:
    def __init__(
        self, sessions: SessionRepository, clock: Clock, credentials: RotatingCredentials, base_url: str
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._credentials = credentials
        self._base_url = base_url

    def current(self) -> Optional[AttendanceSession]:
        """The open session, or None."""
        return self._sessions.find_open()

    def open_session(self) -> AttendanceSession:
        """Open a session; only one may be open at a time (D27)."""
        if self._sessions.find_open() is not None:
            raise SessionAlreadyOpenError()
        try:
            return self._sessions.create(self._clock.now())
        except sqlite3.IntegrityError as exc:  # two requests raced past find_open: the unique index caught it
            raise SessionAlreadyOpenError() from exc

    def close_session(self) -> None:
        """Close the open session; no-op if none (FR-1.13)."""
        open_session = self._sessions.find_open()
        if open_session is not None:
            self._sessions.close(open_session.id, self._clock.now())

    def projector_state(self) -> Optional[ProjectorState]:
        """URL and code for the open session; None when closed so no QR is shown (FR-1.13)."""
        open_session = self._sessions.find_open()
        if open_session is None:
            return None
        token = self._credentials.qr_token(open_session.id)
        return ProjectorState(
            check_in_url=f"{self._base_url}/c/{token}",
            code=self._credentials.current_code(open_session.id),
        )
