"""T20 (D33): no IP / network part left anywhere. Offline; IP literals only from documentation ranges.

Covers R-attendance FR-1.6-FR-1.14, NFR-7, NFR-8, D21, D30, D33.
"""
import csv
import importlib
import io
import logging
import re
import sqlite3
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app import create_app
from app.config import Config
from tests.fakes import FakeClock

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
FORBIDDEN = ["remote_addr", "CF-Connecting-IP", "X-Forwarded-For", "client_ip", "ipaddress", "NetworkPolicy",
             "network_origin"]
SOURCE_SUFFIXES = {".py", ".html", ".js", ".sql"}


def app_sources():
    return [p for p in APP.rglob("*") if p.is_file() and p.suffix in SOURCE_SUFFIXES]


def scan_path(app):
    state = app.extensions["services"]["session_service"].projector_state()
    return state.check_in_url.split("test.example")[1], state.code


def do_check_in(app, nickname="Fox", environ=None, headers=None):
    phone = app.test_client()
    kw = {}
    if environ:
        kw["environ_base"] = environ
    if headers:
        kw["headers"] = headers
    path, code = scan_path(app)
    scanned = phone.get(path, **kw)
    posted = phone.post("/checkin", data={"nickname": nickname, "code": code}, **kw)
    return scanned, posted


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


# ---- 1. no IP read ----------------------------------------------------------------------------

@pytest.mark.parametrize("word", FORBIDDEN)
def test_source_never_mentions_ip_reading(word):
    """Covers T20-1, D33, D21."""
    hits = [str(p) for p in app_sources() if word in p.read_text(encoding="utf-8")]
    assert hits == []


@pytest.mark.parametrize("word", ["allow-list", "allow_list", "allowlist", "relay", "campus", "off campus",
                                  "off_campus", "Apple relay", "relay_ranges", "campus_range"])
def test_no_allow_list_relay_or_origin_vocabulary_in_app(word):
    """Covers T20-3/9: no route, template, JS or config mentions the removed feature."""
    hits = [str(p.relative_to(ROOT)) for p in app_sources()
            if word.lower() in p.read_text(encoding="utf-8").lower()]
    # schema.sql may only mention it in a comment? it must not either
    assert hits == []


def test_poll_js_has_no_origin_text():
    js = (APP / "static" / "poll_json.js").read_text(encoding="utf-8")
    for word in ("off campus", "Apple relay", "origin"):
        assert word not in js


def test_off_campus_message_gone():
    for p in app_sources():
        assert "Check-in is not available right now" not in p.read_text(encoding="utf-8")


# ---- check-in from any address ----------------------------------------------------------------

ORIGINS = [
    ({"REMOTE_ADDR": "192.0.2.7"}, None),
    ({"REMOTE_ADDR": "2001:db8::7"}, None),
    ({"REMOTE_ADDR": "127.0.0.1"}, {"CF-Connecting-IP": "198.51.100.9"}),
    ({"REMOTE_ADDR": "127.0.0.1"}, {"CF-Connecting-IP": "not-an-ip"}),
    ({"REMOTE_ADDR": "127.0.0.1"}, {"CF-Connecting-IP": "1.2.3.4, 5.6.7.8"}),
    ({"REMOTE_ADDR": "127.0.0.1"}, {"X-Forwarded-For": "198.51.100.9"}),
    ({"REMOTE_ADDR": "::1"}, None),
]


@pytest.mark.parametrize("environ,headers", ORIGINS)
def test_check_in_identical_from_any_address(app, environ, headers):
    """Covers T20-1: same success page and same stored row whatever the address."""
    app.extensions["services"]["session_service"].open_session()
    scanned, posted = do_check_in(app, "Fox", environ, headers)
    assert scanned.status_code == 200
    assert posted.status_code == 200 and b"You are checked in" in posted.data and b"Fox" in posted.data
    session = app.extensions["services"]["session_service"].current()
    summary = app.extensions["services"]["session_service"].summary(session.id)
    assert [c.nickname for c in summary.check_ins] == ["Fox"]


def test_same_page_body_for_all_addresses(tmp_path):
    """Covers T20-1: bodies byte-identical across addresses (fresh app each time, same clock)."""
    bodies, rows = [], []
    for i, (environ, headers) in enumerate(ORIGINS):
        cfg = Config(lecturer_pin="1234", secret_key="k", base_url="https://test.example",
                     database_path=str(tmp_path / f"{i}.db"))
        a = create_app(cfg, clock=FakeClock(1_000_000.0))
        a.extensions["services"]["session_service"].open_session()
        _, posted = do_check_in(a, "Fox", environ, headers)
        bodies.append(posted.data)
        conn = sqlite3.connect(cfg.database_path)
        rows.append(conn.execute("SELECT nickname, checked_in_at FROM check_in").fetchall())
        conn.close()
    assert len(set(bodies)) == 1
    assert all(r == rows[0] for r in rows) and rows[0][0][0] == "Fox"


def test_check_in_on_fresh_db_without_settings(app):
    """Covers T20-2: no setting_item row at all."""
    conn = app.extensions["services"]["db"].conn() if "db" in app.extensions["services"] else None
    app.extensions["services"]["session_service"].open_session()
    _, posted = do_check_in(app)
    assert posted.status_code == 200
    if conn is not None:
        assert conn.execute("SELECT COUNT(*) FROM setting_item").fetchone()[0] == 0


# ---- 3. allow-list gone -----------------------------------------------------------------------

@pytest.mark.parametrize("method", ["get", "post"])
def test_allow_list_is_404_with_pin(lecturer, method):
    assert getattr(lecturer, method)("/lecturer/allow-list").status_code == 404


@pytest.mark.parametrize("method", ["get", "post"])
def test_allow_list_is_404_without_pin(client, method):
    assert getattr(client, method)("/lecturer/allow-list").status_code == 404


def test_lecturer_page_links_and_url_for(app, lecturer):
    html = lecturer.get("/lecturer").get_data(as_text=True).lower()
    assert "allow" not in html and "network" not in html and "relay" not in html and "campus" not in html
    from flask import url_for
    from werkzeug.routing import BuildError
    with app.test_request_context():
        with pytest.raises(BuildError):
            url_for("lecturer.allow_list")


# ---- 4. code gone -----------------------------------------------------------------------------

@pytest.mark.parametrize("module", ["app.services.network", "app.adapters.relay_ranges"])
def test_modules_gone(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_files_gone():
    assert not (ROOT / "scripts" / "update_relay_ranges.py").exists()
    assert not (APP / "templates" / "allow_list.html").exists()


def test_errors_module_cleaned():
    import app.errors as errors
    assert not hasattr(errors, "OffCampusError") and not hasattr(errors, "InvalidNetworkRangeError")


def test_no_network_service(app):
    assert "network" not in app.extensions["services"]


# ---- 5. configuration -------------------------------------------------------------------------

def test_config_has_no_relay_path():
    assert not hasattr(Config(lecturer_pin="1", secret_key="k", base_url="http://x"), "relay_ranges_path")


def test_env_example_has_no_relay_line():
    assert "RELAY_RANGES_PATH" not in (ROOT / ".env.example").read_text(encoding="utf-8")


def test_old_env_var_is_ignored():
    cfg = Config.from_env({"LECTURER_PIN": "1", "SECRET_KEY": "k", "BASE_URL": "http://x",
                           "RELAY_RANGES_PATH": "data/x.csv"})
    assert cfg.base_url == "http://x" and not hasattr(cfg, "relay_ranges_path")


def test_gitignore_hygiene():
    """Covers T20-11 (updated): the relay line and comment are gone, minimal repo."""
    text = (ROOT / ".gitignore").read_text(encoding="utf-8").lower()
    assert "relay" not in text and "apple" not in text


def test_git_hygiene_files_not_tracked():
    import subprocess
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    for name in ("app/services/network.py", "app/adapters/relay_ranges.py", "scripts/update_relay_ranges.py",
                 "app/templates/allow_list.html"):
        assert name not in out.splitlines() or not (ROOT / name).exists()
    assert not re.search(r"apple_relay_ranges_.*\.csv", out)


# ---- 6. schema --------------------------------------------------------------------------------

def test_new_schema_check_in_columns(app):
    conn = sqlite3.connect(app.extensions["services"]["config"].database_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(check_in)")]
    assert cols == ["id", "session_id", "device_token", "nickname", "checked_in_at"]
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='setting_item'").fetchone()
    conn.close()


def test_database_has_no_add_column_helper():
    from app.db import Database
    assert not hasattr(Database, "_add_column_if_missing")


# ---- 8/10. JSON and export shape; no IP anywhere ----------------------------------------------

def test_json_keys_exact(app, lecturer):
    session = app.extensions["services"]["session_service"].open_session()
    do_check_in(app, "Fox", {"REMOTE_ADDR": "192.0.2.7"}, {"CF-Connecting-IP": "198.51.100.9"})
    data = lecturer.get(f"/api/sessions/{session.id}/attendance").get_json()
    assert set(data) == {"open", "n", "head_count", "consistency", "check_ins"}
    assert [set(r) for r in data["check_ins"]] == [{"nickname", "checked_in_at"}]


def test_export_columns_exact_and_no_ip(app, lecturer):
    sessions = app.extensions["services"]["session_service"]
    sessions.open_session()
    do_check_in(app, "Fox", {"REMOTE_ADDR": "192.0.2.7"}, {"CF-Connecting-IP": "198.51.100.9"})
    sessions.close_session()
    rows = list(csv.reader(io.StringIO(lecturer.get("/lecturer/export/checkins.csv").get_data().decode("utf-8-sig"))))
    assert rows[0] == ["session date", "nickname", "check-in time"] and len(rows[1]) == 3
    srows = list(csv.reader(io.StringIO(lecturer.get("/lecturer/export/summary.csv").get_data().decode("utf-8-sig"))))
    assert srows[0] == ["session date", "check-ins (N)", "faces detected (D)", "consistency status"]
    wb = load_workbook(io.BytesIO(lecturer.get("/lecturer/export.xlsx").data))
    assert wb.sheetnames == ["Check-ins", "Summary"]
    assert [c.value for c in wb["Check-ins"][1]] == rows[0]
    assert [c.value for c in wb["Summary"][1]] == srows[0]
    blob = str(rows) + str(srows) + str([[c.value for c in r] for ws in wb for r in ws])
    assert "192.0.2" not in blob and "198.51.100" not in blob


def test_no_ip_in_db_or_logs(app, caplog):
    caplog.set_level(logging.DEBUG)
    app.extensions["services"]["session_service"].open_session()
    do_check_in(app, "Fox", {"REMOTE_ADDR": "192.0.2.7"}, {"CF-Connecting-IP": "198.51.100.9"})
    path = app.extensions["services"]["config"].database_path
    conn = sqlite3.connect(path)
    dump = "\n".join(conn.iterdump())
    conn.close()
    assert "192.0.2.7" not in dump and "198.51.100.9" not in dump
    assert "192.0.2.7" not in caplog.text and "198.51.100.9" not in caplog.text


# ---- 7. old T19 database ----------------------------------------------------------------------

OLD_SCHEMA = """
CREATE TABLE attendance_session (id INTEGER PRIMARY KEY AUTOINCREMENT, opened_at REAL NOT NULL, closed_at REAL,
  is_open INTEGER NOT NULL DEFAULT 1 CHECK (is_open IN (0, 1)), head_count INTEGER, head_count_at REAL);
CREATE UNIQUE INDEX one_open_session ON attendance_session(is_open) WHERE is_open = 1;
CREATE TABLE device (device_token TEXT PRIMARY KEY, nickname TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE check_in (id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES attendance_session(id),
  device_token TEXT NOT NULL REFERENCES device(device_token), nickname TEXT NOT NULL, checked_in_at REAL NOT NULL,
  network_origin TEXT NOT NULL DEFAULT 'campus' CHECK (network_origin IN ('campus','apple_relay','off_campus')),
  UNIQUE (session_id, device_token));
CREATE TABLE checkin_window (session_id INTEGER NOT NULL REFERENCES attendance_session(id),
  device_token TEXT NOT NULL, opened_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (session_id, device_token));
CREATE TABLE setting_item (kind TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (kind, value));
INSERT INTO attendance_session(id, opened_at, closed_at, is_open) VALUES (1, 900000.0, 900600.0, 0);
INSERT INTO device VALUES ('old-a', 'Old A', 900000.0), ('old-b', 'Old B', 900000.0);
INSERT INTO check_in(session_id, device_token, nickname, checked_in_at, network_origin)
  VALUES (1, 'old-a', 'Old A', 900010.0, 'campus'), (1, 'old-b', 'Old B', 900020.0, 'off_campus');
INSERT INTO setting_item VALUES ('campus_range', '192.0.2.0/24'), ('campus_range', '2001:db8::/32'),
  ('peer_repo', 'https://github.com/example/peer');
"""


@pytest.fixture
def old_app(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    conn.close()
    cfg = Config(lecturer_pin="1234", secret_key="k", base_url="https://test.example", database_path=str(path))
    return create_app(cfg, clock=FakeClock(1_000_000.0)), path


def test_old_database_untouched_and_usable(old_app):
    """Covers T20-7."""
    app, path = old_app
    client = app.test_client()
    client.post("/lecturer/login", data={"pin": "1234"})
    app.extensions["services"]["db"].init_schema() if "db" in app.extensions["services"] else None
    conn = sqlite3.connect(path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(check_in)")]
    assert "network_origin" in cols
    assert conn.execute("SELECT COUNT(*) FROM setting_item WHERE kind='campus_range'").fetchone()[0] == 2
    # new check-in succeeds, column takes its default
    sessions = app.extensions["services"]["session_service"]
    new = sessions.open_session()
    _, posted = do_check_in(app, "Fox")
    assert posted.status_code == 200 and b"You are checked in" in posted.data
    row = conn.execute("SELECT nickname, network_origin FROM check_in WHERE session_id=?", (new.id,)).fetchone()
    assert row == ("Fox", "campus")
    # old rows still there
    assert conn.execute("SELECT COUNT(*) FROM check_in WHERE session_id=1").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM setting_item WHERE kind='campus_range'").fetchone()[0] == 2
    # JSON of the old and new sessions, no origin
    old_json = client.get("/api/sessions/1/attendance").get_json()
    assert set(old_json) == {"open", "n", "head_count", "consistency", "check_ins"}
    assert [r["nickname"] for r in old_json["check_ins"]] == ["Old A", "Old B"]
    assert all(set(r) == {"nickname", "checked_in_at"} for r in old_json["check_ins"])
    sessions.close_session()
    # export
    rows = list(csv.reader(io.StringIO(client.get("/lecturer/export/checkins.csv").get_data().decode("utf-8-sig"))))
    assert rows[0] == ["session date", "nickname", "check-in time"]
    assert [r[1] for r in rows[1:]] == ["Old A", "Old B", "Fox"]
    assert all(len(r) == 3 for r in rows)
    wb = load_workbook(io.BytesIO(client.get("/lecturer/export.xlsx").data))
    assert [c.value for c in wb["Check-ins"][1]] == ["session date", "nickname", "check-in time"]
    conn.close()


def test_old_database_peer_list_and_idempotent_schema(old_app):
    app, path = old_app
    client = app.test_client()
    client.post("/lecturer/login", data={"pin": "1234"})
    from app.db import Database
    db = Database(str(path))
    db.init_schema()
    db.init_schema()
    page = client.get("/lecturer/peers")
    assert page.status_code == 200 and b"github.com/example/peer" in page.data
    assert b"192.0.2" not in page.data and b"2001:db8" not in page.data
    assert client.get("/lecturer").status_code == 200
