"""SQL for polls, options and votes (D9, D28)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.db import Database, valid_row_id


@dataclass(frozen=True)
class PollOption:
    id: int
    label: str
    votes: int


@dataclass(frozen=True)
class Poll:
    """A question with its options and their live counts."""

    id: int
    question: str
    options: list[PollOption]
    is_open: bool

    def total_votes(self) -> int:
        return sum(option.votes for option in self.options)


class PollRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, question: str, options: list[str], at: float) -> Poll:
        """Insert a poll and its options; raises sqlite3.IntegrityError if another poll is open."""
        with self._db.transaction() as conn:
            poll_id = conn.execute("INSERT INTO poll(question, created_at) VALUES (?, ?)", (question, at)).lastrowid
            conn.executemany(
                "INSERT INTO poll_option(poll_id, position, label) VALUES (?, ?, ?)",
                [(poll_id, position, label) for position, label in enumerate(options, start=1)],
            )
        return self.get(poll_id)

    def _load(self, row: Optional[sqlite3.Row]) -> Optional[Poll]:
        if row is None:
            return None
        option_rows = self._db.conn().execute(
            "SELECT o.id, o.label, COUNT(v.device_token) AS votes FROM poll_option o "
            "LEFT JOIN vote v ON v.option_id = o.id WHERE o.poll_id = ? GROUP BY o.id ORDER BY o.position",
            (row["id"],),
        ).fetchall()
        options = [PollOption(r["id"], r["label"], r["votes"]) for r in option_rows]
        return Poll(row["id"], row["question"], options, bool(row["is_open"]))

    def get(self, poll_id: int) -> Optional[Poll]:
        if not valid_row_id(poll_id):
            return None  # same answer as any unknown id
        return self._load(self._db.conn().execute("SELECT * FROM poll WHERE id = ?", (poll_id,)).fetchone())

    def find_open(self) -> Optional[Poll]:
        return self._load(self._db.conn().execute("SELECT * FROM poll WHERE is_open = 1").fetchone())

    def latest(self) -> Optional[Poll]:
        return self._load(self._db.conn().execute("SELECT * FROM poll ORDER BY id DESC LIMIT 1").fetchone())

    def close(self, poll_id: int, at: float) -> None:
        self._db.conn().execute("UPDATE poll SET is_open = 0, closed_at = ? WHERE id = ?", (at, poll_id))

    def has_voted(self, poll_id: int, device_token: str) -> bool:
        row = self._db.conn().execute(
            "SELECT 1 FROM vote WHERE poll_id = ? AND device_token = ?", (poll_id, device_token)
        ).fetchone()
        return row is not None

    def add_vote(self, poll_id: int, option_id: int, device_token: str, at: float) -> None:
        """Raises sqlite3.IntegrityError if this device already voted in this poll."""
        self._db.conn().execute(
            "INSERT INTO vote(poll_id, device_token, option_id, voted_at) VALUES (?, ?, ?, ?)",
            (poll_id, device_token, option_id, at),
        )
