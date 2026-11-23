"""Extra T2 tests: threads, rollback, constraints, privacy, persistence (test_strategy T2; D3, D21, D27)."""
import sqlite3
import threading

import pytest

from app import create_app
from app.config import Config
from app.db import Database
from app.repositories.checkins import CheckInRepository
from app.repositories.sessions import SessionRepository
from app.repositories.settings import SettingsRepository
from app.repositories.windows import CheckInWindowRepository

FORBIDDEN = {"ip", "ip_address", "client_ip", "remote_addr", "name", "first_name", "last_name", "email",
             "student_id", "phone", "photo", "image", "video"}


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "x.db"))
    d.init_schema()
    return d


def test_second_thread_uses_own_connection_and_sees_committed_data(db):
    """Covers D3: a worker thread reads what the main thread wrote."""
    SessionRepository(db).create(1.0)
    out = []

    def work():
        out.append(SessionRepository(db).find_open())
        out.append(db.conn())

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert out[0] is not None and out[0].opened_at == 1.0
    assert out[1] is not db.conn()


def test_thread_write_visible_to_main(db):
    """Covers D3: write from a second thread."""
    t = threading.Thread(target=lambda: SettingsRepository(db).replace_values("peer_repo", ["a"]))
    t.start()
    t.join()
    assert SettingsRepository(db).list_values("peer_repo") == ["a"]


def test_rollback_discards_all_statements_and_connection_stays_usable(db):
    """Covers D3: block raising rolls back everything."""
    with pytest.raises(ValueError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO attendance_session(opened_at) VALUES (1)")
            conn.execute("INSERT INTO setting_item VALUES ('k','v')")
            raise ValueError
    assert SessionRepository(db).list_all() == []
    assert SettingsRepository(db).list_values("k") == []
    with db.transaction() as conn:  # not stuck in a transaction
        conn.execute("INSERT INTO setting_item VALUES ('k','v')")
    assert SettingsRepository(db).list_values("k") == ["v"]


def test_rollback_on_integrity_error_inside_block(db):
    """Covers D27: constraint failure inside a transaction leaves nothing behind."""
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO attendance_session(opened_at) VALUES (1)")
            conn.execute("INSERT INTO attendance_session(opened_at) VALUES (2)")
    assert SessionRepository(db).list_all() == []


def test_only_one_open_session_then_reopen_after_close(db):
    """Covers D27: partial unique index."""
    s = SessionRepository(db)
    first = s.create(1.0)
    with pytest.raises(sqlite3.IntegrityError):
        s.create(2.0)
    s.close(first.id, 3.0)
    second = s.create(4.0)
    assert s.find_open().id == second.id
    s.close(second.id, 5.0)
    s.close(s.create(6.0).id, 7.0)  # many closed sessions are fine
    assert len(s.list_all()) == 3 and s.find_open() is None
    assert s.get(first.id).closed_at == 3.0


def test_set_head_count_replaces_previous(db):
    """Covers D7."""
    s = SessionRepository(db)
    x = s.create(1.0)
    s.set_head_count(x.id, 10, 2.0)
    s.set_head_count(x.id, 0, 3.0)
    assert s.get(x.id).head_count == 0


def test_unique_session_device_and_nickname_upsert(db):
    """Covers FR-1.12: UNIQUE (session, device)."""
    s, c = SessionRepository(db), CheckInRepository(db)
    a = s.create(1.0)
    c.save_nickname("tok", "Fox", 1.0)
    c.add(a.id, "tok", "Fox", 2.0)
    with pytest.raises(sqlite3.IntegrityError):
        c.add(a.id, "tok", "Fox", 3.0)
    assert c.count_for_session(a.id) == 1
    c.save_nickname("tok", "Owl", 4.0)
    assert c.nickname_of("tok") == "Owl"
    assert c.nickname_of("other") is None
    s.close(a.id, 5.0)
    b = s.create(6.0)
    c.add(b.id, "tok", "Owl", 7.0)  # same device, other session: allowed
    assert c.has_checked_in(b.id, "tok") and c.count_for_session(b.id) == 1


def test_check_in_requires_known_session_and_device(db):
    """Covers FK enforcement."""
    c = CheckInRepository(db)
    with pytest.raises(sqlite3.IntegrityError):
        c.add(99, "nobody", "X", 1.0)


def test_increment_attempts_sequence(db):
    """Covers FR-1.9: 1, 2, 3."""
    s, w = SessionRepository(db), CheckInWindowRepository(db)
    a = s.create(1.0)
    w.open(a.id, "t", 2.0)
    assert [w.increment_attempts(a.id, "t") for _ in range(3)] == [1, 2, 3]
    assert w.find("t").attempts == 3
    w.open(a.id, "t", 3.0)  # rescan resets
    assert w.find("t").attempts == 0
    w.delete(a.id, "t")
    assert w.find("t") is None


def test_window_find_latest_across_sessions(db):
    """Covers FR-1.7: latest window of a device over sessions."""
    s, w = SessionRepository(db), CheckInWindowRepository(db)
    a = s.create(1.0)
    s.close(a.id, 2.0)
    b = s.create(3.0)
    w.open(a.id, "t", 10.0)
    w.open(b.id, "t", 20.0)
    w.open(b.id, "u", 30.0)
    found = w.find("t")
    assert (found.session_id, found.opened_at) == (b.id, 20.0)
    assert w.find("zzz") is None


def test_settings_kinds_isolated_and_dedup_and_order(db):
    """Covers settings: kinds isolated, replace swaps whole list."""
    st = SettingsRepository(db)
    st.replace_values("other_kind", ["a", "b"])
    st.replace_values("peer_repo", ["r1", "r1", "r2"])
    assert st.list_values("peer_repo") == ["r1", "r2"]
    st.replace_values("other_kind", ["c"])
    assert st.list_values("other_kind") == ["c"]
    assert st.list_values("peer_repo") == ["r1", "r2"]
    st.replace_values("other_kind", [])
    assert st.list_values("other_kind") == []
    assert st.list_values("unknown") == []


def test_replace_values_is_atomic_when_it_fails(db):
    """Covers atomic replace: a bad value leaves the old list intact."""
    st = SettingsRepository(db)
    st.replace_values("peer_repo", ["old"])
    with pytest.raises(Exception):
        st.replace_values("peer_repo", ["new", object()])  # unbindable value (None would be silently ignored by OR IGNORE)
    assert st.list_values("peer_repo") == ["old"]


def test_no_personal_or_ip_columns(db):
    """Covers D21, FR-1.3 by introspection."""
    tables = [r[0] for r in db.conn().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    assert {"attendance_session", "device", "check_in", "checkin_window", "setting_item"} <= set(tables)
    cols = {c[1].lower() for t in tables for c in db.conn().execute(f"PRAGMA table_info({t})")}
    assert cols.isdisjoint(FORBIDDEN)


def test_schema_recreate_keeps_data(tmp_path):
    """Covers idempotent schema: second init does not wipe data."""
    path = str(tmp_path / "keep.db")
    d1 = Database(path)
    d1.init_schema()
    SettingsRepository(d1).replace_values("peer_repo", ["a"])
    d2 = Database(path)
    d2.init_schema()
    d2.init_schema()
    assert SettingsRepository(d2).list_values("peer_repo") == ["a"]


def test_data_survives_app_recreation_on_same_file(tmp_path):
    """Covers persistence: restart of the app keeps sessions and check-ins."""
    cfg = Config(lecturer_pin="1234", secret_key="k", base_url="https://t.example",
                 database_path=str(tmp_path / "inst" / "app.db"))
    app1 = create_app(cfg)
    sv = app1.extensions["services"]
    sess = sv["sessions"].create(1.0)
    sv["check_ins"].save_nickname("tok", "Fox", 1.0)
    sv["check_ins"].add(sess.id, "tok", "Fox", 2.0)
    app2 = create_app(cfg)
    sv2 = app2.extensions["services"]
    assert sv2["sessions"].find_open().id == sess.id
    assert [c.nickname for c in sv2["check_ins"].list_for_session(sess.id)] == ["Fox"]
    assert (tmp_path / "inst" / "app.db").exists()


def test_default_database_path_is_under_instance():
    """Covers design: DB file lives under instance/."""
    import inspect
    import app.config as cfg
    assert "instance" in inspect.getsource(cfg)
