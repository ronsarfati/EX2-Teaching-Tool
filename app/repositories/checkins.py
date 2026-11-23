"""SQL for devices (nickname per random token, D6) and check-ins (one per device per session, FR-1.12)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.db import Database


@dataclass(frozen=True)
class CheckIn:
    """A completed check-in. It carries no device token: the table of nicknames is all the lecturer sees."""

    session_id: int
    nickname: str
    checked_in_at: float


def _to_check_in(row: sqlite3.Row) -> CheckIn:
    return CheckIn(row["session_id"], row["nickname"], row["checked_in_at"])


class CheckInRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def nickname_of(self, device_token: str) -> Optional[str]:
        row = self._db.conn().execute("SELECT nickname FROM device WHERE device_token = ?", (device_token,)).fetchone()
        return row["nickname"] if row else None

    def save_nickname(self, device_token: str, nickname: str, at: float) -> None:
        """Remember the nickname of a device (upsert: a device keeps one nickname)."""
        self._db.conn().execute(
            "INSERT INTO device(device_token, nickname, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(device_token) DO UPDATE SET nickname = excluded.nickname",
            (device_token, nickname, at),
        )

    def has_checked_in(self, session_id: int, device_token: str) -> bool:
        row = self._db.conn().execute(
            "SELECT 1 FROM check_in WHERE session_id = ? AND device_token = ?", (session_id, device_token)
        ).fetchone()
        return row is not None

    def add(self, session_id: int, device_token: str, nickname: str, at: float) -> CheckIn:
        """Insert a check-in; raises sqlite3.IntegrityError on a second one for the same device and session."""
        self._db.conn().execute(
            "INSERT INTO check_in(session_id, device_token, nickname, checked_in_at) VALUES (?, ?, ?, ?)",
            (session_id, device_token, nickname, at),
        )
        return CheckIn(session_id, nickname, at)

    def list_for_session(self, session_id: int) -> list[CheckIn]:
        rows = self._db.conn().execute(
            "SELECT session_id, nickname, checked_in_at FROM check_in WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [_to_check_in(row) for row in rows]

    def count_for_session(self, session_id: int) -> int:
        row = self._db.conn().execute("SELECT COUNT(*) AS n FROM check_in WHERE session_id = ?", (session_id,))
        return row.fetchone()["n"]
