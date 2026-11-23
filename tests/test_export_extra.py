"""Extra T12 tests: empty export, multi-session equality with live data, headers, injection, CSV quoting, XLSX, PIN.

Covers FR-1.18, UC-5, D8, D21, D31 (OI-6).
"""
import csv
import io
from datetime import datetime, timezone

import pytest
from openpyxl import load_workbook

from tests.test_export import URLS, check_in, lecturer, read_csv, run_session, services  # noqa: F401

CH_HEADER = ["session date", "nickname", "check-in time"]
SU_HEADER = ["session date", "check-ins (N)", "faces detected (D)", "consistency status"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def sheet_rows(response, name):
    wb = load_workbook(io.BytesIO(response.get_data()))
    return [list(r) for r in wb[name].iter_rows(values_only=True)]


def test_zero_sessions_headers_only_valid_files(lecturer):
    """Covers FR-1.18: no sessions -> headers only, files still valid."""
    assert read_csv(lecturer.get(URLS[0])) == [CH_HEADER]
    assert read_csv(lecturer.get(URLS[1])) == [SU_HEADER]
    assert lecturer.get(URLS[0]).get_data().startswith(b"\xef\xbb\xbf")
    wb = load_workbook(io.BytesIO(lecturer.get(URLS[2]).get_data()))
    assert wb.sheetnames == ["Check-ins", "Summary"]
    assert [[c for c in r] for r in wb["Check-ins"].iter_rows(values_only=True)] == [CH_HEADER]
    assert [[c for c in r] for r in wb["Summary"].iter_rows(values_only=True)] == [SU_HEADER]


@pytest.fixture
def three(app, services, lecturer):
    s1 = run_session(app, services, ["Fox", "Owl"], head_count=2)
    s2 = run_session(app, services, ["Cat"])
    s3 = run_session(app, services, ["Bee", "Ant", "Elk"], head_count=40)
    return [s1, s2, s3]


def test_summary_rows_equal_service_summary(app, services, lecturer, three):
    """Covers FR-1.18, FR-1.16: one summary row per session, equal to SessionService.summary."""
    rows = read_csv(lecturer.get(URLS[1]))
    assert len(rows) == 4
    svc = services["session_service"]
    for row, session in zip(rows[1:], three):
        s = svc.summary(session.id)
        d = s.session.head_count
        assert row[0] == datetime.fromtimestamp(session.opened_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        assert row[1:] == [str(s.n), "" if d is None else str(d), s.consistency or ""]
    assert rows[2][2:] == ["", ""]  # session without photo
    assert rows[1][2] == "2" and rows[3][2] == "40"


def test_checkin_rows_equal_live_api(app, services, lecturer, three):
    """Covers FR-1.18, FR-1.14: check-in rows equal the live API of each session, in order."""
    rows = read_csv(lecturer.get(URLS[0]))[1:]
    expected = []
    for session in three:
        for c in lecturer.get(f"/api/sessions/{session.id}/attendance").get_json()["check_ins"]:
            when = datetime.fromtimestamp(c["checked_in_at"], tz=timezone.utc).strftime("%H:%M:%S")
            expected.append([datetime.fromtimestamp(session.opened_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                             c["nickname"], when])
    assert len(rows) == 6 and rows == expected


def test_headers_exact_and_no_ip_token_device(app, services, lecturer, three):
    """Covers D21, NFR-7: exact headers; nothing identifying in any file or sheet."""
    forbidden = ("ip", "token", "device", "address", "cookie")
    for url, header in ((URLS[0], CH_HEADER), (URLS[1], SU_HEADER)):
        rows = read_csv(lecturer.get(url))
        assert rows[0] == header
        assert not any(f in h.lower() for h in rows[0] for f in forbidden)
        assert "192.0.2" not in lecturer.get(url).get_data(as_text=True)
    wb = load_workbook(io.BytesIO(lecturer.get(URLS[2]).get_data()))
    for name, header in (("Check-ins", CH_HEADER), ("Summary", SU_HEADER)):
        assert [c.value for c in wb[name][1]] == header
        for row in wb[name].iter_rows(values_only=True):
            assert all("192.0.2" not in str(v) for v in row)


@pytest.mark.parametrize("nickname", ["=1+1", "+1", "-1", "@a", "\tx", "\rx"])
def test_each_dangerous_prefix_neutralised(app, services, lecturer, nickname):
    """Covers D31: every trigger char gets a leading apostrophe (what the app stores, after any trim)."""
    run_session(app, services, [nickname])
    stored = [c["nickname"] for c in lecturer.get(
        "/api/sessions/1/attendance").get_json()["check_ins"]]
    if not stored:
        pytest.skip("nickname rejected by validation")
    value = read_csv(lecturer.get(URLS[0]))[1][1]
    assert value == "'" + stored[0] if stored[0][:1] in "=+-@\t\r" else value == stored[0]
    assert not value.startswith(("=", "+", "-", "@", "\t", "\r"))


@pytest.mark.parametrize("nickname", ["Fox", "Mary Ann", "a=b", "x-y", "o'neil"])
def test_normal_nickname_unaltered(app, services, lecturer, nickname):
    """Covers D31: benign nicknames (trigger chars not leading) are untouched."""
    run_session(app, services, [nickname])
    assert read_csv(lecturer.get(URLS[0]))[1][1] == nickname
    sheet = load_workbook(io.BytesIO(lecturer.get(URLS[2]).get_data()))["Check-ins"]
    assert sheet["B2"].value == nickname


@pytest.mark.parametrize("nickname", ["a,b", 'say "hi"', "line1\nline2"])
def test_csv_special_characters_round_trip(app, services, lecturer, nickname):
    """Covers FR-1.18: comma, quote, newline survive csv quoting (if the app accepts them)."""
    run_session(app, services, [nickname])
    stored = lecturer.get("/api/sessions/1/attendance").get_json()["check_ins"]
    if not stored:
        pytest.skip("nickname rejected by validation")
    rows = read_csv(lecturer.get(URLS[0]))
    assert len(rows) == 2 and rows[1][1] == stored[0]["nickname"]


def test_exporter_direct_special_characters(app, services):
    """Covers FR-1.18: exporter itself round-trips comma/quote/newline (bypasses nickname validation)."""
    exporter = services["exporter"]
    sess = services["session_service"].open_session()
    names = ["a,b", 'say "hi"', "l1\nl2"]
    for i, n in enumerate(names):
        exporter._check_ins._db.conn().execute(
            "INSERT INTO device(device_token, nickname, created_at) VALUES (?, ?, ?)", (f"t{i}", n, 0.0))
        exporter._check_ins.add(sess.id, f"t{i}", n, 1_700_000_000.0 + i)
    rows = list(csv.reader(io.StringIO(exporter.checkins_csv().decode("utf-8-sig"))))
    assert [r[1] for r in rows[1:]] == names
    wb = load_workbook(io.BytesIO(exporter.xlsx()))
    assert [r[1] for r in wb["Check-ins"].iter_rows(min_row=2, values_only=True)] == names


def test_xlsx_row_counts_match_csv(app, services, lecturer, three):
    """Covers FR-1.18: XLSX has 2 sheets whose row counts match the CSVs."""
    wb = load_workbook(io.BytesIO(lecturer.get(URLS[2]).get_data()))
    assert len(wb.sheetnames) == 2
    assert wb["Check-ins"].max_row == len(read_csv(lecturer.get(URLS[0]))) == 7
    assert wb["Summary"].max_row == len(read_csv(lecturer.get(URLS[1]))) == 4
    assert [c.value for c in wb["Summary"][3]][2:] == [None, None]


@pytest.mark.parametrize("url,mime,name", [
    (URLS[0], "text/csv", "checkins.csv"), (URLS[1], "text/csv", "summary.csv"), (URLS[2], XLSX_MIME, "attendance.xlsx")])
def test_headers_content_type_and_disposition(lecturer, url, mime, name):
    """Covers UC-5: download headers."""
    r = lecturer.get(url)
    assert r.status_code == 200 and r.mimetype == mime
    assert r.headers["Content-Disposition"].startswith("attachment") and name in r.headers["Content-Disposition"]


@pytest.mark.parametrize("url", URLS)
def test_no_pin_redirects_without_content(app, services, client, url):
    """Covers D8: without PIN, redirect to login and no file content, even with data present."""
    run_session(app, services, ["Fox"])
    r = client.get(url)
    assert r.status_code == 302 and "/lecturer/login" in r.headers["Location"]
    assert b"Fox" not in r.get_data() and b"session date" not in r.get_data()
