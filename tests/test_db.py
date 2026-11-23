"""Database: schema, pragmas, transactions, threads, privacy of columns (D3, D21, FR-1.3)."""
import threading

import pytest

from app.db import Database

FORBIDDEN_COLUMNS = {"ip", "ip_address", "client_ip", "name", "first_name", "last_name", "email",
                     "student_id", "photo", "image"}


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(str(tmp_path / "sub" / "t.db"))  # also checks the parent folder is created
    database.init_schema()
    return database


def test_init_schema_is_idempotent(db):
    db.init_schema()


def test_pragmas(db):
    assert db.conn().execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.conn().execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_transaction_commits(db):
    with db.transaction() as conn:
        conn.execute("INSERT INTO setting_item VALUES ('k', 'v')")
    assert db.conn().execute("SELECT COUNT(*) FROM setting_item").fetchone()[0] == 1


def test_transaction_rolls_back_on_error(db):
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO setting_item VALUES ('k', 'v')")
            raise RuntimeError("boom")
    assert db.conn().execute("SELECT COUNT(*) FROM setting_item").fetchone()[0] == 0


def test_each_thread_gets_its_own_connection(db):
    seen = []
    thread = threading.Thread(target=lambda: seen.append(db.conn()))
    thread.start()
    thread.join()
    assert seen[0] is not db.conn()
    assert db.conn() is db.conn()


def test_no_personal_data_column(db):
    tables = [r[0] for r in db.conn().execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]  # skip SQLite's own tables
    columns = {c[1].lower() for t in tables for c in db.conn().execute(f"PRAGMA table_info({t})")}
    assert columns.isdisjoint(FORBIDDEN_COLUMNS)
    assert "nickname" in columns
