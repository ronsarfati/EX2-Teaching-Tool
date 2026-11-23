"""Generic storage of lecturer-edited lists: kind 'peer_repo' (homework review comparison list)."""
from __future__ import annotations

from app.db import Database


class SettingsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def list_values(self, kind: str) -> list[str]:
        rows = self._db.conn().execute("SELECT value FROM setting_item WHERE kind = ? ORDER BY rowid", (kind,))
        return [row["value"] for row in rows]

    def replace_values(self, kind: str, values: list[str]) -> None:
        """Swap the whole list of one kind atomically; other kinds are untouched. Duplicates are dropped."""
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM setting_item WHERE kind = ?", (kind,))
            conn.executemany(
                "INSERT OR IGNORE INTO setting_item(kind, value) VALUES (?, ?)", [(kind, v) for v in values]
            )
