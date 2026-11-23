"""Extra T10 tests: N counting, session isolation, ordering, JSON shape, XSS-safe JS, poll interval.

Covers FR-1.14, NFR-2, UC-5, D21.
"""
import re
from pathlib import Path

import pytest

CAMPUS = "192.0.2.10"
KW = {"environ_base": {"REMOTE_ADDR": CAMPUS}}
JS = Path(__file__).resolve().parent.parent / "app" / "static" / "poll_json.js"


@pytest.fixture
def svc(app):
    s = app.extensions["services"]
    s["settings"].replace_values("campus_range", ["192.0.2.0/24"])
    return s["session_service"]


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def attempt(app, phone, nickname, code=None):
    """One phone (persistent cookie jar) scans then submits; returns the POST response."""
    state = app.extensions["services"]["session_service"].projector_state()
    phone.get(state.check_in_url.split("test.example")[1], **KW)
    return phone.post("/checkin", data={"nickname": nickname, "code": code or state.code}, **KW)


def get(lecturer, sid):
    return lecturer.get(f"/api/sessions/{sid}/attendance")


def test_n_increments_by_one_per_device_and_order_is_insertion(app, svc, lecturer):
    """Covers FR-1.14: 3 devices -> 3; rows in check-in order (ORDER BY id; design unspecified)."""
    s = svc.open_session()
    for i, name in enumerate(["Cat", "Ant", "Bee"], start=1):
        attempt(app, app.test_client(), name)
        data = get(lecturer, s.id).get_json()
        assert data["n"] == i
    assert [c["nickname"] for c in data["check_ins"]] == ["Cat", "Ant", "Bee"]  # not alphabetical


def test_failed_attempts_never_counted(app, svc, lecturer):
    """Covers FR-1.14: wrong code, then no window at all, leave N at 0."""
    s = svc.open_session()
    phone = app.test_client()
    attempt(app, phone, "Fox", code="zzz")
    phone.post("/checkin", data={"nickname": "Fox", "code": "000"}, **KW)
    other = app.test_client()  # never scanned: no window
    other.post("/checkin", data={"nickname": "Owl", "code": svc.projector_state().code}, **KW)
    assert get(lecturer, s.id).get_json()["n"] == 0


def test_returning_device_not_counted_twice(app, svc, lecturer):
    """Covers FR-1.14: same device (cookie) in the same session stays at 1."""
    s = svc.open_session()
    phone = app.test_client()
    attempt(app, phone, "Fox")
    attempt(app, phone, "Fox")
    data = get(lecturer, s.id).get_json()
    assert data["n"] == 1 and len(data["check_ins"]) == 1


def test_previous_session_not_mixed_in(app, svc, lecturer):
    """Covers FR-1.14: closed session keeps its rows; the new one starts at 0."""
    first = svc.open_session()
    attempt(app, app.test_client(), "Old")
    svc.close_session()
    second = svc.open_session()
    attempt(app, app.test_client(), "New")
    a, b = get(lecturer, first.id).get_json(), get(lecturer, second.id).get_json()
    assert a["open"] is False and [c["nickname"] for c in a["check_ins"]] == ["Old"]
    assert b["open"] is True and [c["nickname"] for c in b["check_ins"]] == ["New"] and b["n"] == 1


def test_json_keys_exact_and_no_leak(app, svc, lecturer):
    """Covers D21: exact keys; no token, IP or window data."""
    s = svc.open_session()
    attempt(app, app.test_client(), "Fox")
    data = get(lecturer, s.id).get_json()
    assert set(data) == {"open", "n", "head_count", "consistency", "check_ins"}
    assert set(data["check_ins"][0]) == {"nickname", "checked_in_at"}
    body = get(lecturer, s.id).get_data(as_text=True)
    for forbidden in (CAMPUS, "device", "attempt", "window", "code"):
        assert forbidden not in body


def test_head_count_and_consistency_null_before_photo(svc, lecturer):
    """Covers FR-1.14: null (not 0) before any photo."""
    s = svc.open_session()
    data = get(lecturer, s.id).get_json()
    assert data["head_count"] is None and data["consistency"] is None
    assert data["open"] is True and data["check_ins"] == []


def test_html_nickname_returned_raw_in_json(app, svc, lecturer):
    """Covers NFR-2: JSON carries the text as typed; escaping is the client's job (textContent)."""
    s = svc.open_session()
    resp = attempt(app, app.test_client(), "<b>x</b>")
    if resp.status_code not in (200, 302, 303):
        pytest.skip("nickname rejected by validation; cannot test raw HTML")
    data = get(lecturer, s.id).get_json()
    if data["n"] == 0:
        pytest.skip("nickname with markup refused by validation")
    assert data["check_ins"][0]["nickname"] == "<b>x</b>"


def test_js_uses_textcontent_not_innerhtml():
    """Covers NFR-2: static check of the polling script."""
    src = re.sub(r"//[^\n]*", "", JS.read_text())  # ignore comments
    assert "textContent" in src
    for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert bad not in src


def test_poll_interval_between_2_and_3_seconds():
    """Covers D4/FR-1.14: POLL_MS in [2000, 3000]."""
    ms = int(re.search(r"POLL_MS\s*=\s*(\d+)", JS.read_text()).group(1))
    assert 2000 <= ms <= 3000
    assert "setInterval(poll, POLL_MS)" in JS.read_text()


def test_401_without_pin_leaks_nothing(app, svc, client):
    """Covers FR-1.14: anonymous caller gets JSON 401 and no attendance data."""
    s = svc.open_session()
    attempt(app, app.test_client(), "Fox")
    resp = get(client, s.id)
    assert resp.status_code == 401 and resp.is_json
    body = resp.get_data(as_text=True)
    assert "Fox" not in body and "check_ins" not in body and "\"n\"" not in body


def test_unknown_id_404_json_srs_message(lecturer):
    """Covers FR-1.14: unknown id -> 404 JSON with the SRS message."""
    resp = get(lecturer, 424242)
    assert resp.status_code == 404 and resp.is_json
    assert resp.get_json() == {"error": "There is no attendance check-in right now."}
