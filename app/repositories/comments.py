"""SQL for anonymous comments (D29): only text and time are stored."""
from __future__ import annotations

from dataclasses import dataclass

from app.db import Database


@dataclass(frozen=True)
class Comment:
    id: int
    text: str
    created_at: float


class CommentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, text: str, at: float) -> Comment:
        cursor = self._db.conn().execute("INSERT INTO comment(text, created_at) VALUES (?, ?)", (text, at))
        return Comment(cursor.lastrowid, text, at)

    def list_recent(self, limit: int) -> list[Comment]:
        """Newest first; the id breaks ties between comments posted in the same instant."""
        rows = self._db.conn().execute(
            "SELECT id, text, created_at FROM comment ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Comment(r["id"], r["text"], r["created_at"]) for r in rows]
