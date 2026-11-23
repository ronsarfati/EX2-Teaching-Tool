"""SQL for the 1-minute check-in windows opened by a QR scan (FR-1.7, FR-1.9)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.db import Database


@dataclass(frozen=True)
class CheckInWindow:
    session_id: int
    device_token: str
    opened_at: float
    attempts: int


class CheckInWindowRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def open(self, session_id: int, device_token: str, at: float) -> None:
        """Start a window with 0 attempts, replacing any previous one (scanning again starts over)."""
        self._db.conn().execute(
            "INSERT OR REPLACE INTO checkin_window(session_id, device_token, opened_at, attempts) VALUES (?, ?, ?, 0)",
            (session_id, device_token, at),
        )

    def find(self, device_token: str) -> Optional[CheckInWindow]:
        """Most recent window of this device, whatever the session."""
        row = self._db.conn().execute(
            "SELECT * FROM checkin_window WHERE device_token = ? ORDER BY opened_at DESC, session_id DESC LIMIT 1",
            (device_token,),
        ).fetchone()
        if row is None:
            return None
        return CheckInWindow(row["session_id"], row["device_token"], row["opened_at"], row["attempts"])

    def increment_attempts(self, session_id: int, device_token: str) -> int:
        """Count one more code attempt and return the new total."""
        row = self._db.conn().execute(
            "UPDATE checkin_window SET attempts = attempts + 1 WHERE session_id = ? AND device_token = ? "
            "RETURNING attempts",
            (session_id, device_token),
        ).fetchone()
        return row["attempts"]

    def delete(self, session_id: int, device_token: str) -> None:
        self._db.conn().execute(
            "DELETE FROM checkin_window WHERE session_id = ? AND device_token = ?", (session_id, device_token)
        )
