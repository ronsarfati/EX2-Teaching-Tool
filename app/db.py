"""SQLite access (D3): one connection per thread, idempotent schema, explicit transactions."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
BUSY_TIMEOUT_MS = 5000
SQLITE_MAX_INT = 2**63 - 1  # larger Python ints make the sqlite3 driver raise OverflowError

# Old rows predate the feature (D32): they were all accepted on the campus ranges, hence the default.
NETWORK_ORIGIN_COLUMN = (
    "TEXT NOT NULL DEFAULT 'campus' CHECK (network_origin IN ('campus', 'apple_relay', 'off_campus'))"
)


def valid_row_id(value: int) -> bool:
    """True if `value` can be a row id. Lookups treat any other id exactly like an unknown one (404, not 500)."""
    return 0 <= value <= SQLITE_MAX_INT


class Database:
    """Hands out a connection per thread (sqlite3 connections must not be shared across threads)."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._local = threading.local()

    def conn(self) -> sqlite3.Connection:
        """Return this thread's connection, opening it on first use."""
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = self._open()
            self._local.connection = connection
        return connection

    def _open(self) -> sqlite3.Connection:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: autocommit, so transaction() alone decides when BEGIN/COMMIT happen.
        connection = sqlite3.connect(self._path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")  # readers (polling) do not block the writer
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block atomically. IMMEDIATE takes the write lock up front, so check-then-write is race-free."""
        connection = self.conn()
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")

    def init_schema(self) -> None:
        """Create the tables if they do not exist yet, then add columns introduced after the first release."""
        self.conn().executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self._add_column_if_missing("check_in", "network_origin", NETWORK_ORIGIN_COLUMN)

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        """Upgrade a database created before `column` existed; CREATE TABLE IF NOT EXISTS never alters one.

        Names and definition are constants of this module, never user input.
        """
        connection = self.conn()
        existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
