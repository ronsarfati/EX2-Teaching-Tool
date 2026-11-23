"""Student check-in pages, end to end with the test client (T8)."""
import re

import pytest


@pytest.fixture
def open_session(app, clock):
    """Open a session and return it."""
    s = app.extensions["services"]
    session = s["session_service"].open_session()
    return session


def scan_url(app):
    return app.extensions["services"]["session_service"].projector_state().check_in_url.split("test.example")[1]


def code_now(app, session):
    return app.extensions["services"]["session_service"].projector_state().code


def phone(app):
    return app.test_client(), {}


def test_menu(client):
    response = client.get("/")
    assert response.status_code == 200 and b"/checkin" in response.data


def test_first_visit_shows_nickname_warning_and_numeric_code(app, open_session):
    c, kw = phone(app)
    response = c.get(scan_url(app), **kw)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'name="nickname"' in html and 'maxlength="30"' in html
    assert "do not use your real name or ID" in html
    assert 'inputmode="numeric"' in html and 'pattern="[0-9]{4}"' in html and "Confirm" in html
    assert html.index('name="nickname"') < html.index('name="code"')
    cookie = response.headers["Set-Cookie"]
    assert "dt=" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_success_then_already_checked_in(app, open_session):
    c, kw = phone(app)
    c.get(scan_url(app), **kw)
    response = c.post("/checkin", data={"nickname": "Fox", "code": code_now(app, open_session)}, **kw)
    assert response.status_code == 200 and b"You are checked in" in response.data and b"Fox" in response.data
    again = c.get(scan_url(app), **kw)
    assert again.status_code == 409 and b"You are already checked in for this class." in again.data


def test_returning_device_has_no_nickname_field(app, open_session, clock):
    c, kw = phone(app)
    c.get(scan_url(app), **kw)
    c.post("/checkin", data={"nickname": "Fox", "code": code_now(app, open_session)}, **kw)
    app.extensions["services"]["session_service"].close_session()
    app.extensions["services"]["session_service"].open_session()
    response = c.get(scan_url(app), **kw)
    html = response.get_data(as_text=True)
    assert 'name="nickname"' not in html and 'name="code"' in html
    assert "Set-Cookie" not in response.headers  # cookie already present


def test_wrong_code(app, open_session):
    c, kw = phone(app)
    c.get(scan_url(app), **kw)
    wrong = f"{(int(code_now(app, open_session)) + 1) % 10000:04d}"
    response = c.post("/checkin", data={"nickname": "Fox", "code": wrong}, **kw)
    assert response.status_code == 400 and b"Wrong code. Type the code shown under the QR now." in response.data


def test_empty_nickname(app, open_session):
    c, kw = phone(app)
    c.get(scan_url(app), **kw)
    response = c.post("/checkin", data={"nickname": "  ", "code": "1234"}, **kw)
    assert b"Please choose a nickname (not your real name or ID)." in response.data


def test_post_without_scan_window_expired(app, open_session):
    c, kw = phone(app)
    response = c.post("/checkin", data={"nickname": "Fox", "code": "1234"}, **kw)
    assert response.status_code == 400 and b"Your check-in time ran out. Scan the QR code again." in response.data


def test_window_runs_out(app, open_session, clock):
    c, kw = phone(app)
    c.get(scan_url(app), **kw)
    clock.advance(61)
    response = c.post("/checkin", data={"nickname": "Fox", "code": code_now(app, open_session)}, **kw)
    assert b"Your check-in time ran out." in response.data


def test_too_many_attempts(app, open_session):
    c, kw = phone(app)
    c.get(scan_url(app), **kw)
    wrong = f"{(int(code_now(app, open_session)) + 1) % 10000:04d}"
    for _ in range(5):
        c.post("/checkin", data={"nickname": "Fox", "code": wrong}, **kw)
    response = c.post("/checkin", data={"nickname": "Fox", "code": wrong}, **kw)
    assert response.status_code == 429 and b"Too many tries. Scan the QR code again." in response.data


def test_expired_qr(app, open_session, clock):
    c, kw = phone(app)
    url = scan_url(app)
    clock.advance(60)
    response = c.get(url, **kw)
    assert b"This QR code has expired. Scan a fresh one." in response.data


def test_closed_session(app, open_session):
    c, kw = phone(app)
    url = scan_url(app)
    app.extensions["services"]["session_service"].close_session()
    response = c.get(url, **kw)
    assert response.status_code == 409 and b"Attendance for this class is closed." in response.data


def test_checkin_without_token_no_session(app):
    c, kw = phone(app)
    response = c.get("/checkin", **kw)
    assert response.status_code == 404 and b"There is no attendance check-in right now." in response.data


def test_checkin_without_token_session_open(app, open_session):
    c, kw = phone(app)
    response = c.get("/checkin", **kw)
    assert response.status_code == 400 and b"Scan the QR code on the projector." in response.data


def test_errors_leak_no_internals(app, open_session):
    c, kw = phone(app)
    response = c.get("/c/garbage", **kw)
    assert b"Traceback" not in response.data and b"Error:" not in response.data
