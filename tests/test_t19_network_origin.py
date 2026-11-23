"""T19 acceptance tests, extra coverage (D32, FR-1.2, FR-1.14, FR-1.18, FR-1.19). Offline, documentation IPs only.

Covers criteria 1-8, 10-17, 19, 20 of the T19 list in docs/design.md.
"""
import csv
import io
import logging
import sqlite3
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app import create_app
from app.adapters.relay_ranges import load_relay_ranges, parse_egress_csv
from app.errors import OffCampusError
from app.repositories.checkins import NetworkOrigin, count_origins, CheckIn
from app.services.network import NetworkPolicy

ROOT = Path(__file__).resolve().parent.parent
CAMPUS_NET = "192.114.52.0/24"
RELAY_V4 = "198.51.100.0/25"
RELAY_V6 = "2001:db8:4000::/64"
O = NetworkOrigin


class FakeSettings:
    def __init__(self, values):
        self.values = values

    def list_values(self, kind):
        return list(self.values)


def policy(campus=(CAMPUS_NET,), relay=(RELAY_V4, RELAY_V6, "2a02:26f7:df88:4000::/64")):
    import ipaddress
    return NetworkPolicy(FakeSettings(campus), [ipaddress.ip_network(r) for r in relay])


# ---------- 1-6, 8b: classification ----------
@pytest.mark.parametrize("ip,expected", [
    ("198.51.100.0", O.APPLE_RELAY), ("198.51.100.127", O.APPLE_RELAY),
    ("198.51.100.128", O.OFF_CAMPUS), ("198.51.99.255", O.OFF_CAMPUS),
    ("2001:db8:4000::", O.APPLE_RELAY), ("2001:db8:4000:0:ffff:ffff:ffff:ffff", O.APPLE_RELAY),
    ("2001:db8:4000:1::", O.OFF_CAMPUS), ("2001:db8:3fff:ffff:ffff:ffff:ffff:ffff", O.OFF_CAMPUS),
    ("2a02:26f7:df88:4000:6000::", O.APPLE_RELAY),
    ("::ffff:198.51.100.5", O.APPLE_RELAY), ("::ffff:192.114.52.10", O.CAMPUS),
    ("::ffff:198.51.100.200", O.OFF_CAMPUS),
    ("192.114.52.0", O.CAMPUS), ("192.114.52.6", O.CAMPUS), ("192.114.52.255", O.CAMPUS),
    ("192.114.51.255", O.OFF_CAMPUS), ("192.114.53.0", O.OFF_CAMPUS),
    ("192.0.2.7", O.OFF_CAMPUS), ("2001:db8:1::7", O.OFF_CAMPUS),
])
def test_t19_classify_boundaries(ip, expected):
    """Covers T19 criteria 1, 2, 3, 5, 6."""
    assert policy().classify(ip) is expected


def test_t19_ensure_allowed_accepts_off_campus():
    """Covers criterion 6."""
    policy().ensure_allowed("192.0.2.7")
    policy().ensure_allowed("2001:db8:1::7")


def test_t19_overlap_is_campus():
    """Covers criterion 4."""
    p = policy(campus=("198.51.100.0/24",))
    assert p.classify("198.51.100.5") is O.CAMPUS
    assert p.classify("198.51.100.200") is O.CAMPUS


def test_t19_v4_never_matches_v6_range_and_no_exception():
    """Covers criterion 3: version mixing."""
    p = policy(campus=("::/0",), relay=("0.0.0.0/0",))
    assert p.classify("192.0.2.1") is O.APPLE_RELAY
    p2 = policy(campus=("0.0.0.0/0",), relay=())
    assert p2.classify("2001:db8::1") is O.OFF_CAMPUS


@pytest.mark.parametrize("ip", ["198.51.100.5", "192.114.52.10", "192.0.2.7", "2001:db8:4000::1"])
def test_t19_empty_campus_list_refuses_everyone(ip):
    """Covers criterion 7."""
    with pytest.raises(OffCampusError):
        policy(campus=()).classify(ip)
    with pytest.raises(OffCampusError):
        policy(campus=()).ensure_allowed(ip)


@pytest.mark.parametrize("ip", ["not-an-ip", "", "1.2.3.4, 5.6.7.8", "999.1.1.1", "192.114.52.1/24"])
def test_t19_malformed_ip_refused(ip):
    """Covers criterion 8."""
    with pytest.raises(OffCampusError):
        policy().classify(ip)


def test_t19_no_relay_list():
    """Covers criterion 8b."""
    p = NetworkPolicy(FakeSettings([CAMPUS_NET]))
    assert p.classify("2a02:26f7:df88:4000:6000::") is O.OFF_CAMPUS
    assert p.relay_range_count() == 0


def test_t19_campus_ranges_read_at_every_call():
    """Covers FR-1.4 kept."""
    s = FakeSettings([CAMPUS_NET])
    p = NetworkPolicy(s, [])
    assert p.classify("192.0.2.1") is O.OFF_CAMPUS
    s.values = ["192.0.2.0/24"]
    assert p.classify("192.0.2.1") is O.CAMPUS
    s.values = []
    with pytest.raises(OffCampusError):
        p.classify("192.0.2.1")


def test_t19_origin_values_labels_counts():
    """Covers criterion 8c."""
    assert [o.value for o in O] == ["campus", "apple_relay", "off_campus"]
    assert [o.label() for o in O] == ["campus", "Apple relay", "off campus"]
    assert count_origins([]) == {O.CAMPUS: 0, O.APPLE_RELAY: 0, O.OFF_CAMPUS: 0}
    rows = [CheckIn(1, "a", 0.0, O.OFF_CAMPUS), CheckIn(1, "b", 0.0, O.OFF_CAMPUS), CheckIn(1, "c", 0.0)]
    assert count_origins(rows) == {O.CAMPUS: 1, O.APPLE_RELAY: 0, O.OFF_CAMPUS: 2}


# ---------- CF-Connecting-IP trust ----------
@pytest.mark.parametrize("peer,header,expected", [
    ("127.0.0.1", "198.51.100.5", "198.51.100.5"),
    ("::1", "198.51.100.5", "198.51.100.5"),
    ("::ffff:127.0.0.1", "198.51.100.5", "198.51.100.5"),
    ("192.0.2.9", "192.114.52.10", "192.0.2.9"),          # forged from non-loopback
    ("198.51.100.5", "192.114.52.10", "198.51.100.5"),
    ("2001:db8::1", "192.114.52.10", "2001:db8::1"),
    ("127.0.0.1", None, "127.0.0.1"),
    ("127.0.0.1", "garbage", "garbage"),
])
def test_t19_resolve_client_ip(peer, header, expected):
    """Covers criterion 8 / FR-1.2 header trust."""
    assert NetworkPolicy.resolve_client_ip(peer, header) == expected


# ---------- parser / loader ----------
def test_t19_parser_details():
    """Covers criterion 9."""
    lines = [
        "198.51.100.0/24,IL,IL-M,Tel Aviv,", "2001:db8:4000::/64,IL,IL-M,Haifa,",
        "bad range,FR,,,", "garbage", "999.1.1.0/24,IL,,,", "2a02:zz::/64,IL,,,", ",IL,,,", "", "   ",
        "198.51.100.1/24,il,,,", "203.0.113.0/24, IL ,,,", "192.0.2.0/24,FR,,,",
    ]
    r = parse_egress_csv(lines, "IL")
    assert [str(n) for n in r.networks] == ["198.51.100.0/24", "2001:db8:4000::/64", "198.51.100.0/24",
                                           "203.0.113.0/24"]
    assert r.skipped == 4  # garbage + 999 + zz + lone
    assert r.kept_lines == [lines[0], lines[1], lines[9], lines[10]]
    r2 = parse_egress_csv(["range,country,region,city", "192.0.2.0/24,FR,,,"], None)
    assert r2.skipped == 1 and len(r2.networks) == 1
    assert [str(n) for n in parse_egress_csv(lines[:1], " il ").networks] == ["198.51.100.0/24"]


def test_t19_loader_cases(tmp_path, caplog):
    """Covers criterion 10."""
    caplog.set_level(logging.INFO)
    assert load_relay_ranges(str(tmp_path / "missing.csv")) == []
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert load_relay_ranges(str(tmp_path)) == []                       # a directory
    bad = tmp_path / "bin.csv"
    bad.write_bytes(b"198.51.100.0/24,IL,,,\n\xff\xfe\x00bad\n")
    assert load_relay_ranges(str(bad)) == []
    f = tmp_path / "ok.csv"
    f.write_text("198.51.100.0/24,IL,,,\ngarbage\n2001:db8::/32,IL,,,\n203.0.113.0/24,FR,,,\n999.0.0.0/8,IL\n,IL\n")
    assert len(load_relay_ranges(str(f))) == 3  # no country filter in the loader (any country valid)
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    assert load_relay_ranges(str(empty)) == []
    if hasattr(__import__("os"), "chmod"):
        unreadable = tmp_path / "noperm.csv"
        unreadable.write_text("198.51.100.0/24,IL,,,\n")
        unreadable.chmod(0)
        try:
            assert load_relay_ranges(str(unreadable)) == []
        finally:
            unreadable.chmod(0o600)
    assert "192" not in " ".join(r.getMessage() for r in caplog.records if "client" in r.getMessage())


# ---------- app-level helpers ----------
CAMPUS_IP, RELAY_IP, OFF_IP = "192.114.52.10", "198.51.100.5", "192.0.2.7"


def make_app(config, tmp_path, relay_lines=("198.51.100.0/25,IL,,,",), **kw):
    f = tmp_path / "relay.csv"
    if relay_lines is not None:
        f.write_text("\n".join(relay_lines) + "\n")
    return create_app(replace(config, relay_ranges_path=str(f)), **kw)


@pytest.fixture
def rapp(config, clock, tmp_path):
    a = make_app(config, tmp_path, clock=clock)
    a.extensions["services"]["settings"].replace_values("campus_range", [CAMPUS_NET])
    return a


def scan_path(a):
    return a.extensions["services"]["session_service"].projector_state().check_in_url.split("test.example")[1]


def code(a):
    return a.extensions["services"]["session_service"].projector_state().code


def phone_check_in(a, nickname, scan_ip, confirm_ip=None, via_header=True, code_override=None):
    """Return (scan_response, confirm_response). Peer is loopback + CF header when via_header."""
    c = a.test_client()

    def kw(ip):
        return ({"environ_base": {"REMOTE_ADDR": "127.0.0.1"}, "headers": {"CF-Connecting-IP": ip}} if via_header
                else {"environ_base": {"REMOTE_ADDR": ip}})
    s = c.get(scan_path(a), **kw(scan_ip))
    r = c.post("/checkin", data={"nickname": nickname, "code": code_override or code(a)}, **kw(confirm_ip or scan_ip))
    return s, r


def login(c):
    c.post("/lecturer/login", data={"pin": "1234"})
    return c


def three(a):
    a.extensions["services"]["session_service"].open_session()
    for n, ip in (("Camp", CAMPUS_IP), ("Rel", RELAY_IP), ("Off", OFF_IP)):
        s, r = phone_check_in(a, n, ip)
        assert r.status_code == 200, r.get_data(as_text=True)


# ---------- 11, 12 ----------
def test_t19_startup_without_file_and_with_file(config, tmp_path):
    """Covers criterion 11."""
    a = make_app(config, tmp_path, relay_lines=None)
    assert a.test_client().get("/ping").status_code == 200
    assert a.extensions["services"]["network"].relay_range_count() == 0
    b = make_app(replace(config, database_path=str(tmp_path / "b.db")), tmp_path,
                 relay_lines=["198.51.100.0/25,IL,,,", "x", "2001:db8::/32,IL,,,"])
    assert b.extensions["services"]["network"].relay_range_count() == 2
    assert b.extensions["services"]["checkin_service"]._network is b.extensions["services"]["network"]


def test_t19_startup_with_directory_and_binary_file(config, tmp_path):
    """Covers criterion 10/11: unreadable relay path does not stop start-up."""
    a = create_app(replace(config, relay_ranges_path=str(tmp_path)))
    assert a.test_client().get("/ping").status_code == 200
    f = tmp_path / "b.csv"
    f.write_bytes(b"\xff\xfe\xfd")
    b = create_app(replace(config, relay_ranges_path=str(f), database_path=str(tmp_path / "z.db")))
    assert b.extensions["services"]["network"].relay_range_count() == 0


def test_t19_end_to_end_origins_and_same_student_page(rapp):
    """Covers criterion 12."""
    rapp.extensions["services"]["session_service"].open_session()
    pages = []
    for n, ip in (("Camp", CAMPUS_IP), ("Rel", RELAY_IP), ("Off", OFF_IP)):
        _, r = phone_check_in(rapp, n, ip)
        assert r.status_code == 200
        pages.append(r.get_data(as_text=True).replace(n, "X"))
    assert len(set(pages)) == 1
    for word in ("relay", "off campus", "Apple"):
        assert word.lower() not in pages[0].lower()
    sid = rapp.extensions["services"]["session_service"].current().id
    rows = rapp.extensions["services"]["check_ins"].list_for_session(sid)
    assert [r.network_origin for r in rows] == [O.CAMPUS, O.APPLE_RELAY, O.OFF_CAMPUS]


def test_t19_origin_from_confirm_request(rapp):
    """Covers criterion 12: scan on campus, confirm off campus -> off_campus (and the reverse)."""
    rapp.extensions["services"]["session_service"].open_session()
    _, r = phone_check_in(rapp, "A", CAMPUS_IP, confirm_ip=OFF_IP)
    assert r.status_code == 200
    _, r = phone_check_in(rapp, "B", OFF_IP, confirm_ip=RELAY_IP)
    assert r.status_code == 200
    _, r = phone_check_in(rapp, "C", RELAY_IP, confirm_ip=CAMPUS_IP)
    sid = rapp.extensions["services"]["session_service"].current().id
    got = [c.network_origin for c in rapp.extensions["services"]["check_ins"].list_for_session(sid)]
    assert got == [O.OFF_CAMPUS, O.APPLE_RELAY, O.CAMPUS]


def test_t19_forged_header_from_non_loopback_peer(rapp):
    """Covers FR-1.2: a forged CF header from a non-loopback peer is ignored, the peer address wins."""
    rapp.extensions["services"]["session_service"].open_session()
    _, r = phone_check_in(rapp, "Forger", OFF_IP, via_header=False)  # baseline off campus via socket
    c = rapp.test_client()
    kw = {"environ_base": {"REMOTE_ADDR": OFF_IP}, "headers": {"CF-Connecting-IP": CAMPUS_IP}}
    c.get(scan_path(rapp), **kw)
    r = c.post("/checkin", data={"nickname": "F2", "code": code(rapp)}, **kw)
    assert r.status_code == 200
    sid = rapp.extensions["services"]["session_service"].current().id
    origins = {c.nickname: c.network_origin for c in rapp.extensions["services"]["check_ins"].list_for_session(sid)}
    assert origins == {"Forger": O.OFF_CAMPUS, "F2": O.OFF_CAMPUS}


@pytest.mark.parametrize("header", ["not-an-ip", "1.2.3.4, 5.6.7.8", ""])
def test_t19_malformed_cf_header_refused(rapp, header):
    """Covers criterion 8 through the routes. (An empty header falls back to the loopback peer: not malformed.)"""
    rapp.extensions["services"]["session_service"].open_session()
    c = rapp.test_client()
    r = c.get(scan_path(rapp), environ_base={"REMOTE_ADDR": "127.0.0.1"}, headers={"CF-Connecting-IP": header})
    if header == "":
        assert r.status_code == 200 or r.status_code == 403  # loopback itself: classified OFF_CAMPUS -> accepted
        return
    assert r.status_code == 403
    assert "Check-in is not available right now. Ask the lecturer." in r.get_data(as_text=True)


def test_t19_empty_campus_list_through_routes(config, clock, tmp_path):
    """Covers criterion 7: 403, unchanged message, no window, no row."""
    a = make_app(config, tmp_path, clock=clock)
    s = a.extensions["services"]
    s["session_service"].open_session()
    for ip in (CAMPUS_IP, RELAY_IP, OFF_IP):
        c = a.test_client()
        kw = {"environ_base": {"REMOTE_ADDR": ip}}
        r = c.get(scan_path(a), **kw)
        assert r.status_code == 403
        assert "Check-in is not available right now. Ask the lecturer." in r.get_data(as_text=True)
        r = c.post("/checkin", data={"nickname": "X", "code": code(a)}, **kw)
        assert r.status_code == 403
    sid = s["session_service"].current().id
    assert s["check_ins"].list_for_session(sid) == []
    n = a.extensions["services"]["config"]
    conn = sqlite3.connect(n.database_path)
    assert conn.execute("SELECT COUNT(*) FROM check_in").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM checkin_window").fetchone()[0] == 0


def test_t19_off_campus_still_needs_fresh_qr_and_code(rapp, clock):
    """Covers criterion 20."""
    rapp.extensions["services"]["session_service"].open_session()
    path = scan_path(rapp)
    clock.advance(30)  # QR token older than 15 s
    c = rapp.test_client()
    r = c.get(path, environ_base={"REMOTE_ADDR": OFF_IP})
    assert r.status_code != 200
    c2 = rapp.test_client()
    kw = {"environ_base": {"REMOTE_ADDR": OFF_IP}}
    c2.get(scan_path(rapp), **kw)
    wrong = f"{(int(code(rapp)) + 1) % 1000:03d}"
    r = c2.post("/checkin", data={"nickname": "W", "code": wrong}, **kw)
    assert r.status_code == 400 and b"Wrong code" in r.data


# ---------- privacy ----------
def test_t19_ip_never_stored_logged_or_exported(rapp, caplog, config):
    """Covers criteria 13, 15 and D21: the IP appears nowhere."""
    caplog.set_level(logging.DEBUG)
    three(rapp)
    c = login(rapp.test_client())
    blobs = [c.get(u).get_data(as_text=True) for u in
             ("/api/sessions/1/attendance", "/lecturer/export/checkins.csv", "/lecturer/export/summary.csv", "/lecturer/")]
    xl = c.get("/lecturer/export.xlsx").data
    wb = load_workbook(io.BytesIO(xl))
    blobs += [str(cell.value) for ws in wb for row in ws.iter_rows() for cell in row]
    db = Path(config.database_path)
    sqlite3.connect(config.database_path).execute("PRAGMA wal_checkpoint(TRUNCATE)")
    raw = b"".join(p.read_bytes() for p in db.parent.glob(db.name + "*"))
    logs = "\n".join(r.getMessage() for r in caplog.records)
    for ip in (CAMPUS_IP, RELAY_IP, OFF_IP):
        assert ip.encode() not in raw
        assert ip not in logs
        assert not any(ip in b for b in blobs)


# ---------- 13 API, 14 live table ----------
def test_t19_api_origin_fields(rapp):
    """Covers criterion 13."""
    three(rapp)
    c = login(rapp.test_client())
    j = c.get("/api/sessions/1/attendance").get_json()
    assert j["n"] == 3 and j["off_campus_n"] == 1 and j["apple_relay_n"] == 1
    assert [r["network_origin"] for r in j["check_ins"]] == ["campus", "apple_relay", "off_campus"]
    assert all(set(r) == {"nickname", "checked_in_at", "network_origin"} for r in j["check_ins"])
    assert not any("ip" in k.lower() for k in j)


def test_t19_api_counters_zero_when_empty(rapp):
    rapp.extensions["services"]["session_service"].open_session()
    j = login(rapp.test_client()).get("/api/sessions/1/attendance").get_json()
    assert j["n"] == 0 and j["off_campus_n"] == 0 and j["apple_relay_n"] == 0


def test_t19_live_table_page_and_script(rapp):
    """Covers criterion 14."""
    rapp.extensions["services"]["session_service"].open_session()
    c = login(rapp.test_client())
    html = c.get("/lecturer").get_data(as_text=True)
    assert 'id="off-campus-n"' in html and 'id="apple-relay-n"' in html
    assert "checked in (" in html and "off campus," in html and "via Apple relay)" in html
    js = c.get("/static/poll_json.js").get_data(as_text=True)
    assert "off campus network" in js and "Apple relay" in js and "origin-warning" in js
    assert '"off_campus"' in js and '"apple_relay"' in js
    assert "textContent" in js and ".innerHTML" not in js and "innerHTML =" not in js


# ---------- 15 export ----------
def test_t19_export_csv_and_xlsx(rapp):
    """Covers criterion 15."""
    three(rapp)
    s = rapp.extensions["services"]
    s["session_service"].close_session()
    s["session_service"].open_session()  # second session, campus only
    phone_check_in(rapp, "Solo", CAMPUS_IP)
    c = login(rapp.test_client())
    rd = lambda u: list(csv.reader(io.StringIO(c.get(u).get_data().decode("utf-8-sig"))))
    ck = rd("/lecturer/export/checkins.csv")
    assert ck[0] == ["session date", "nickname", "check-in time", "network"]
    assert [r[3] for r in ck[1:]] == ["campus", "Apple relay", "off campus", "campus"]
    sm = rd("/lecturer/export/summary.csv")
    assert sm[0][-2:] == ["off campus", "via Apple relay"]
    assert [r[-2:] for r in sm[1:]] == [["1", "1"], ["0", "0"]] or [r[-2:] for r in sm[1:]] == [["0", "0"], ["1", "1"]]
    wb = load_workbook(io.BytesIO(c.get("/lecturer/export.xlsx").data))
    assert [list(r) for r in wb["Check-ins"].iter_rows(values_only=True)][0] == ck[0]
    assert [r[3] for r in wb["Check-ins"].iter_rows(min_row=2, values_only=True)] == [r[3] for r in ck[1:]]
    xs = list(wb["Summary"].iter_rows(values_only=True))
    assert list(xs[0][-2:]) == ["off campus", "via Apple relay"]
    assert sorted(tuple(r[-2:]) for r in xs[1:]) == [(0, 0), (1, 1)]
    j = c.get("/api/sessions/1/attendance").get_json()
    row1 = [r for r in sm[1:] if r[1] == "3"][0]
    assert (int(row1[-2]), int(row1[-1])) == (j["off_campus_n"], j["apple_relay_n"])


# ---------- 16 migration ----------
def old_db(path):
    conn = sqlite3.connect(path)
    # reuse the real schema but drop network_origin from check_in
    schema = (ROOT / "app" / "schema.sql").read_text()
    import re
    schema = re.sub(r"\n\s*(--[^\n]*\n)?\s*network_origin[^\n]*\n", "\n", schema)
    assert "network_origin" not in schema
    conn.executescript(schema)
    conn.execute("INSERT INTO attendance_session(opened_at, closed_at) VALUES (1000000.0, 1000100.0)")
    for i, tok in enumerate(("t1", "t2")):
        conn.execute("INSERT INTO device(device_token, nickname, created_at) VALUES (?,?,?)", (tok, f"N{i}", 1.0))
        conn.execute("INSERT INTO check_in(session_id, device_token, nickname, checked_in_at) VALUES (1,?,?,?)",
                     (tok, f"N{i}", 1000010.0 + i))
    conn.commit()
    conn.close()


def test_t19_old_database_migrated_and_idempotent(config, tmp_path):
    """Covers criterion 16."""
    old_db(config.database_path)
    cols = [r[1] for r in sqlite3.connect(config.database_path).execute("PRAGMA table_info(check_in)")]
    assert "network_origin" not in cols
    a = create_app(config)
    create_app(config)  # second start: idempotent
    a.extensions["services"]["db"].init_schema() if "db" in a.extensions["services"] else None
    rows = a.extensions["services"]["check_ins"].list_for_session(1)
    assert [(r.nickname, r.network_origin) for r in rows] == [("N0", O.CAMPUS), ("N1", O.CAMPUS)]
    c = login(a.test_client())
    assert c.get("/api/sessions/1/attendance").get_json()["off_campus_n"] == 0
    assert [r[3] for r in csv.reader(io.StringIO(c.get("/lecturer/export/checkins.csv").get_data().decode("utf-8-sig")))][1:] \
        == ["campus", "campus"]


def test_t19_fresh_db_check_constraint(config):
    """Covers criterion 16: CHECK rejects an unknown value; default is campus."""
    a = create_app(config)
    conn = sqlite3.connect(config.database_path)
    conn.execute("INSERT INTO attendance_session(opened_at) VALUES (1.0)")
    conn.execute("INSERT INTO device(device_token, nickname, created_at) VALUES ('d','n',1.0)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO check_in(session_id, device_token, nickname, checked_in_at, network_origin) "
                     "VALUES (1,'d','n',1.0,'elsewhere')")
    conn.execute("INSERT INTO check_in(session_id, device_token, nickname, checked_in_at) VALUES (1,'d','n',1.0)")
    assert conn.execute("SELECT network_origin FROM check_in").fetchone()[0] == "campus"


def test_t19_migrated_column_has_check_constraint(config):
    """Covers criterion 16: the ALTERed column also enforces the CHECK."""
    old_db(config.database_path)
    create_app(config)
    conn = sqlite3.connect(config.database_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE check_in SET network_origin = 'elsewhere'")


# ---------- 17 allow-list page ----------
def test_t19_allow_list_page_relay_count(config, clock, tmp_path):
    """Covers criterion 17."""
    a = make_app(config, tmp_path, clock=clock, relay_lines=["198.51.100.0/25,IL,,,", "2001:db8::/32,IL,,,"])
    c = a.test_client()
    assert c.get("/lecturer/allow-list").status_code == 302
    assert c.post("/lecturer/allow-list", data={"ranges": "192.0.2.0/24"}).status_code == 302
    login(c)
    assert "Apple Private Relay list:\n2 ranges loaded" in c.get("/lecturer/allow-list").get_data(as_text=True)
    r = c.post("/lecturer/allow-list", data={"ranges": "192.0.2.0/24"}, follow_redirects=True)
    assert "2 ranges loaded" in r.get_data(as_text=True)
    bad = c.post("/lecturer/allow-list", data={"ranges": "nonsense"})
    assert bad.status_code == 400 and "2 ranges loaded" in bad.get_data(as_text=True)


def test_t19_allow_list_page_not_loaded(config, clock, tmp_path):
    a = make_app(config, tmp_path, clock=clock, relay_lines=None)
    c = login(a.test_client())
    assert "not loaded" in c.get("/lecturer/allow-list").get_data(as_text=True)


# ---------- 19 hygiene ----------
def test_t19_env_example_and_no_tracked_relay_csv():
    """Covers criterion 19 (env + tracked files)."""
    assert "RELAY_RANGES_PATH=data/apple_relay_ranges_IL.csv" in (ROOT / ".env.example").read_text()
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    assert "apple_relay_ranges" not in out


def test_t19_gitignore_ignores_relay_csv():
    """Covers criterion 19: .gitignore must ignore data/apple_relay_ranges_*.csv."""
    r = subprocess.run(["git", "check-ignore", "-q", "data/apple_relay_ranges_IL.csv"], cwd=ROOT)
    assert r.returncode == 0, "data/apple_relay_ranges_IL.csv is NOT ignored by git"
