"""Apple relay ranges (D32): parser, loader, classification, migration. Documentation addresses only, no network."""
import ipaddress
import sqlite3
from dataclasses import replace

import pytest

from app import create_app
from app.adapters.relay_ranges import load_relay_ranges, parse_egress_csv
from app.db import Database
from app.repositories.checkins import NetworkOrigin, count_origins
from app.repositories.settings import SettingsRepository
from app.services.network import NetworkPolicy

LINES = ["198.51.100.0/25,IL,IL-01,Tel Aviv,", "2001:db8:4000::/64,IL,IL-01,Tel Aviv,", "192.0.2.0/24,FR,FR-75,Paris,",
         "garbage", "999.1.1.0/24,IL,,,", "", ",IL,,,"]


def test_parser_keeps_only_valid_lines_of_the_country():
    parsed = parse_egress_csv(LINES, "il")
    assert [str(n) for n in parsed.networks] == ["198.51.100.0/25", "2001:db8:4000::/64"]
    assert parsed.kept_lines == LINES[:2]
    assert parsed.skipped == 3  # garbage, bad IPv4, empty range; the FR row and the blank line are not counted


def test_loader_never_raises(tmp_path):
    assert load_relay_ranges(str(tmp_path / "missing.csv")) == []
    assert load_relay_ranges(str(tmp_path)) == []
    good = tmp_path / "r.csv"
    good.write_text("\n".join(LINES[:2] + ["junk"]), encoding="utf-8")
    assert len(load_relay_ranges(str(good))) == 2


@pytest.fixture
def policy(tmp_path):
    db = Database(str(tmp_path / "n.db"))
    db.init_schema()
    relay = [ipaddress.ip_network("198.51.100.0/25"), ipaddress.ip_network("2001:db8:4000::/64")]
    p = NetworkPolicy(SettingsRepository(db), relay)
    p.save_ranges(["192.114.52.0/24", "198.51.100.64/28"])
    return p


@pytest.mark.parametrize("ip, expected", [
    ("192.114.52.10", NetworkOrigin.CAMPUS),
    ("198.51.100.0", NetworkOrigin.APPLE_RELAY),
    ("198.51.100.127", NetworkOrigin.APPLE_RELAY),
    ("198.51.100.128", NetworkOrigin.OFF_CAMPUS),
    ("198.51.100.70", NetworkOrigin.CAMPUS),  # in both lists: campus wins
    ("::ffff:198.51.100.5", NetworkOrigin.APPLE_RELAY),
    ("2001:db8:4000:0:ffff:ffff:ffff:ffff", NetworkOrigin.APPLE_RELAY),
    ("2001:db8:4000:1::", NetworkOrigin.OFF_CAMPUS),
])
def test_classify(policy, ip, expected):
    assert policy.classify(ip) is expected


def test_origin_labels_and_counts():
    assert [o.label() for o in NetworkOrigin] == ["campus", "Apple relay", "off campus"]
    assert count_origins([]) == {o: 0 for o in NetworkOrigin}


def test_app_starts_without_relay_file_and_shares_one_policy(config, tmp_path):
    missing = create_app(replace(config, relay_ranges_path=str(tmp_path / "none.csv")))
    assert missing.test_client().get("/ping").data == b"ok"
    assert missing.extensions["services"]["network"].relay_range_count() == 0
    relay_file = tmp_path / "r.csv"
    relay_file.write_text(LINES[0] + "\n", encoding="utf-8")
    app = create_app(replace(config, relay_ranges_path=str(relay_file)))
    services = app.extensions["services"]
    assert services["network"].relay_range_count() == 1
    assert services["checkin_service"]._network is services["network"]


def test_old_database_gets_the_column_and_keeps_rows(tmp_path):
    path = str(tmp_path / "old.db")
    raw = sqlite3.connect(path)
    raw.executescript(
        "CREATE TABLE attendance_session (id INTEGER PRIMARY KEY AUTOINCREMENT, opened_at REAL NOT NULL, closed_at REAL,"
        " is_open INTEGER NOT NULL DEFAULT 1, head_count INTEGER, head_count_at REAL);"
        "CREATE TABLE device (device_token TEXT PRIMARY KEY, nickname TEXT NOT NULL, created_at REAL NOT NULL);"
        "CREATE TABLE check_in (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, device_token TEXT NOT NULL,"
        " nickname TEXT NOT NULL, checked_in_at REAL NOT NULL, UNIQUE (session_id, device_token));"
        "INSERT INTO attendance_session(opened_at) VALUES (1.0);"
        "INSERT INTO device VALUES ('t', 'Fox', 1.0);"
        "INSERT INTO check_in(session_id, device_token, nickname, checked_in_at) VALUES (1, 't', 'Fox', 2.0);"
    )
    raw.close()
    db = Database(path)
    db.init_schema()
    db.init_schema()  # idempotent
    row = db.conn().execute("SELECT network_origin FROM check_in").fetchone()
    assert row["network_origin"] == "campus"
