"""F1 repositories on a temporary SQLite file."""
import sqlite3

import pytest

from app.db import Database
from app.repositories.checkins import CheckInRepository
from app.repositories.sessions import SessionRepository
from app.repositories.settings import SettingsRepository
from app.repositories.windows import CheckInWindowRepository


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(str(tmp_path / "t.db"))
    database.init_schema()
    return database


@pytest.fixture
def sessions(db):
    return SessionRepository(db)


@pytest.fixture
def check_ins(db):
    return CheckInRepository(db)


@pytest.fixture
def windows(db):
    return CheckInWindowRepository(db)


@pytest.fixture
def settings(db):
    return SettingsRepository(db)


def test_session_create_get_round_trip(sessions):
    created = sessions.create(100.0)
    assert created.is_open() and created.head_count is None
    assert sessions.get(created.id) == created
    assert sessions.find_open() == created


def test_session_get_unknown_is_none(sessions):
    assert sessions.get(999) is None
    assert sessions.find_open() is None


def test_second_open_session_violates_index(sessions):
    sessions.create(100.0)
    with pytest.raises(sqlite3.IntegrityError):
        sessions.create(200.0)


def test_close_allows_a_new_session(sessions):
    first = sessions.create(100.0)
    sessions.close(first.id, 150.0)
    closed = sessions.get(first.id)
    assert not closed.is_open() and closed.closed_at == 150.0
    assert sessions.find_open() is None
    second = sessions.create(200.0)
    assert [s.id for s in sessions.list_all()] == [first.id, second.id]


def test_head_count_is_replaced_by_a_new_photo(sessions):
    s = sessions.create(100.0)
    sessions.set_head_count(s.id, 42, 110.0)
    sessions.set_head_count(s.id, 40, 120.0)
    assert sessions.get(s.id).head_count == 40


def test_nickname_round_trip(check_ins):
    assert check_ins.nickname_of("tok") is None
    check_ins.save_nickname("tok", "Fox", 1.0)
    assert check_ins.nickname_of("tok") == "Fox"


def test_check_in_add_list_count(sessions, check_ins):
    s = sessions.create(100.0)
    check_ins.save_nickname("a", "Fox", 1.0)
    check_ins.save_nickname("b", "Owl", 1.0)
    assert not check_ins.has_checked_in(s.id, "a")
    added = check_ins.add(s.id, "a", "Fox", 10.0)
    check_ins.add(s.id, "b", "Owl", 20.0)
    assert (added.session_id, added.nickname, added.checked_in_at) == (s.id, "Fox", 10.0)
    assert check_ins.has_checked_in(s.id, "a") and not check_ins.has_checked_in(s.id, "zzz")
    assert [c.nickname for c in check_ins.list_for_session(s.id)] == ["Fox", "Owl"]
    assert check_ins.count_for_session(s.id) == 2


def test_duplicate_check_in_violates_unique(sessions, check_ins):
    s = sessions.create(100.0)
    check_ins.save_nickname("a", "Fox", 1.0)
    check_ins.add(s.id, "a", "Fox", 10.0)
    with pytest.raises(sqlite3.IntegrityError):
        check_ins.add(s.id, "a", "Fox", 11.0)


def test_window_open_find_and_attempts(sessions, windows):
    s = sessions.create(100.0)
    windows.open(s.id, "tok", 105.0)
    found = windows.find("tok")
    assert (found.session_id, found.opened_at, found.attempts) == (s.id, 105.0, 0)
    assert [windows.increment_attempts(s.id, "tok") for _ in range(3)] == [1, 2, 3]
    windows.open(s.id, "tok", 110.0)  # scanning again starts over
    assert windows.find("tok").attempts == 0


def test_window_find_returns_most_recent_across_sessions(sessions, windows):
    old = sessions.create(100.0)
    sessions.close(old.id, 150.0)
    new = sessions.create(200.0)
    windows.open(old.id, "tok", 105.0)
    windows.open(new.id, "tok", 205.0)
    assert windows.find("tok").session_id == new.id


def test_window_delete_and_unknown_token(sessions, windows):
    s = sessions.create(100.0)
    windows.open(s.id, "tok", 105.0)
    assert windows.find("other") is None
    windows.delete(s.id, "tok")
    assert windows.find("tok") is None


def test_settings_round_trip_and_isolation(settings):
    settings.replace_values("other_kind", ["x", "y"])
    settings.replace_values("peer_repo", ["https://github.com/a/b"])
    assert settings.list_values("other_kind") == ["x", "y"]
    settings.replace_values("other_kind", [])
    assert settings.list_values("other_kind") == []
    assert settings.list_values("peer_repo") == ["https://github.com/a/b"]


def test_settings_replace_overwrites_and_drops_duplicates(settings):
    settings.replace_values("peer_repo", ["a", "b"])
    settings.replace_values("peer_repo", ["c", "c"])
    assert settings.list_values("peer_repo") == ["c"]


def test_create_app_wires_repositories(app):
    services = app.extensions["services"]
    assert services["sessions"].find_open() is None
