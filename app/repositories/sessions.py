"""SQL for attendance sessions (D27: one open at a time, enforced by a partial unique index)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.db import Database, valid_row_id


@dataclass(frozen=True)
class AttendanceSession:
    """One class meeting during which students can check in."""

    id: int
    opened_at: float
    closed_at: Optional[float]
    head_count: Optional[int]

    def is_open(self) -> bool:
        return self.closed_at is None


def _to_session(row: sqlite3.Row) -> AttendanceSession:
    return AttendanceSession(row["id"], row["opened_at"], row["closed_at"], row["head_count"])


class SessionRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, opened_at: float) -> AttendanceSession:
        """Insert an open session; raises sqlite3.IntegrityError if another one is open."""
        cursor = self._db.conn().execute("INSERT INTO attendance_session(opened_at) VALUES (?)", (opened_at,))
        return AttendanceSession(cursor.lastrowid, opened_at, None, None)

    def get(self, session_id: int) -> Optional[AttendanceSession]:
        if not valid_row_id(session_id):
            return None  # same answer as any unknown id
        row = self._db.conn().execute("SELECT * FROM attendance_session WHERE id = ?", (session_id,)).fetchone()
        return _to_session(row) if row else None

    def find_open(self) -> Optional[AttendanceSession]:
        row = self._db.conn().execute("SELECT * FROM attendance_session WHERE is_open = 1").fetchone()
        return _to_session(row) if row else None

    def close(self, session_id: int, closed_at: float) -> None:
        self._db.conn().execute(
            "UPDATE attendance_session SET is_open = 0, closed_at = ? WHERE id = ?", (closed_at, session_id)
        )

    def set_head_count(self, session_id: int, count: int, at: float) -> None:
        """Store the photo count; a later photo replaces the previous one (D7)."""
        self._db.conn().execute(
            "UPDATE attendance_session SET head_count = ?, head_count_at = ? WHERE id = ?", (count, at, session_id)
        )

    def list_all(self) -> list[AttendanceSession]:
        rows = self._db.conn().execute("SELECT * FROM attendance_session ORDER BY id").fetchall()
        return [_to_session(row) for row in rows]
