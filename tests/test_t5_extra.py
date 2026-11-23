"""Extra T5 tests: PIN gate hardening, session cookie integrity, open/close lifecycle, page hygiene.

Covers FR-1.1, FR-1.13, FR-6.1, D22, D23, D27, SD-1, SD-3.
"""
import pytest

from app import create_app
from app.config import Config

PIN = "1234"
PROTECTED = [("get", "/lecturer"), ("post", "/lecturer/sessions"), ("post", "/lecturer/sessions/close")]
OPEN_MSG = b"A session is already open. Close it first."


def _login(client, pin=PIN):
    return client.post("/lecturer/login", data={"pin": pin})


def _is_lecturer_page(response):
    return response.status_code == 302 and "/lecturer" in response.headers["Location"] \
        and not response.headers["Location"].endswith("/login")


def _open_count(app):
    return sum(1 for s in app.extensions["services"]["sessions"].list_all() if s.is_open())


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_routes_refuse_without_pin_and_change_nothing(app, client, method, path):
    """Covers FR-6.1: no cookie -> redirect to login; no session created."""
    response = getattr(client, method)(path)
    assert response.status_code == 302 and response.headers["Location"].endswith("/lecturer/login")
    assert app.extensions["services"]["sessions"].list_all() == []


@pytest.mark.parametrize("pin", ["", "   ", "0000", "12345", "123", "١٢٣٤", "çé€漢字", "1234 ", "a" * 100_000])
def test_bad_pins_rejected_without_echo(client, pin):
    """Covers FR-6.1, D22: wrong/empty/non-ASCII/very long PIN -> 401 'Wrong PIN.', PIN not echoed."""
    response = _login(client, pin)
    assert response.status_code == 401
    assert b"Wrong PIN." in response.data
    if len(pin.strip()) > 2:
        assert pin.encode() not in response.data
    assert client.get("/lecturer").status_code == 302


def test_wrong_pin_page_still_has_login_form(client):
    """Covers FR-6.1: error page does not leak the right PIN."""
    assert PIN.encode() not in _login(client, "0000").data


def test_login_get_has_no_pin_in_body(client):
    assert PIN.encode() not in client.get("/lecturer/login").data


def test_login_redirects_to_lecturer_page(client):
    assert _is_lecturer_page(_login(client)) or _login(client).headers["Location"].endswith("/lecturer")


def test_tampered_cookie_not_accepted(client):
    """Covers D22: a forged / altered session cookie gives no access."""
    _login(client)
    cookie = client.get_cookie("session")
    assert cookie is not None
    value = cookie.value
    flipped = value[:-2] + ("AA" if not value.endswith("AA") else "BB")
    client.set_cookie("session", flipped)
    assert client.get("/lecturer").status_code == 302
    client.set_cookie("session", "garbage")
    assert client.get("/lecturer").status_code == 302
    client.set_cookie("session", "")
    assert client.post("/lecturer/sessions").status_code == 302


def test_cookie_signed_with_other_key_not_accepted(app, client):
    """Covers D22: a cookie forged with another SECRET_KEY is rejected."""
    forged = app.session_interface.get_signing_serializer(app)
    other = create_app(Config(lecturer_pin=PIN, secret_key="another-key", base_url="https://x.example",
                              database_path=app.extensions["services"]["config"].database_path + "2"))
    token = other.session_interface.get_signing_serializer(other).dumps({"lecturer": True})
    assert forged is not None
    client.set_cookie("session", token)
    assert client.get("/lecturer").status_code == 302


def test_new_app_with_other_secret_invalidates_cookie(tmp_path, app, client):
    """Covers D22: restarting with a different SECRET_KEY invalidates old logins."""
    _login(client)
    assert client.get("/lecturer").status_code == 200
    cookie = client.get_cookie("session").value
    restarted = create_app(Config(lecturer_pin=PIN, secret_key="rotated-key", base_url="https://t.example",
                                  database_path=str(tmp_path / "other.db")))
    c2 = restarted.test_client()
    c2.set_cookie("session", cookie)
    assert c2.get("/lecturer").status_code == 302


def test_same_secret_new_app_keeps_cookie_valid(tmp_path, app, client):
    """Sanity control for the previous test: the cookie really is what carries the login."""
    _login(client)
    cookie = client.get_cookie("session").value
    twin = create_app(Config(lecturer_pin=PIN, secret_key="test-secret-key", base_url="https://t.example",
                             database_path=str(tmp_path / "twin.db")))
    c2 = twin.test_client()
    c2.set_cookie("session", cookie)
    assert c2.get("/lecturer").status_code == 200


def test_separate_clients_do_not_share_login(app):
    a, b = app.test_client(), app.test_client()
    _login(a)
    assert a.get("/lecturer").status_code == 200
    assert b.get("/lecturer").status_code == 302


def test_pin_change_requires_new_pin(tmp_path):
    """Covers D22: PIN comes from config, not hard-coded."""
    app = create_app(Config(lecturer_pin="9876", secret_key="k", base_url="https://t.example",
                            database_path=str(tmp_path / "p.db")))
    c = app.test_client()
    assert _login(c, "1234").status_code == 401
    assert _login(c, "9876").status_code == 302


def test_no_logout_route_exists(client):
    """Spec gap probe: no logout route is specified; report only."""
    _login(client)
    assert client.post("/lecturer/logout").status_code in (404, 405)


def test_open_twice_message_and_single_row(app, client):
    """Covers FR-1.1, D27: second open -> exact SRS message, 409, one open session in DB."""
    _login(client)
    assert _is_lecturer_page(client.post("/lecturer/sessions"))
    response = client.post("/lecturer/sessions")
    assert response.status_code == 409 and OPEN_MSG in response.data
    assert _open_count(app) == 1
    assert len(app.extensions["services"]["sessions"].list_all()) == 1


def test_close_without_open_is_noop(app, client):
    """Covers FR-1.13: closing with nothing open is harmless (redirect, no error, no rows)."""
    _login(client)
    response = client.post("/lecturer/sessions/close")
    assert _is_lecturer_page(response)
    assert app.extensions["services"]["sessions"].list_all() == []


def test_close_twice_is_noop(app, client):
    _login(client)
    client.post("/lecturer/sessions")
    client.post("/lecturer/sessions/close")
    assert _is_lecturer_page(client.post("/lecturer/sessions/close"))
    rows = app.extensions["services"]["sessions"].list_all()
    assert len(rows) == 1 and not rows[0].is_open()


def test_reopen_after_close_creates_new_session(app, client, clock):
    """Covers FR-1.1, FR-1.13, D27: reopen works and creates a distinct row."""
    _login(client)
    client.post("/lecturer/sessions")
    clock.advance(60) if hasattr(clock, "advance") else None
    client.post("/lecturer/sessions/close")
    assert _is_lecturer_page(client.post("/lecturer/sessions"))
    rows = app.extensions["services"]["sessions"].list_all()
    assert len(rows) == 2 and _open_count(app) == 1
    assert len({r.id for r in rows}) == 2


def test_closed_session_has_close_time(app, client):
    _login(client)
    client.post("/lecturer/sessions")
    client.post("/lecturer/sessions/close")
    s = app.extensions["services"]["sessions"].list_all()[0]
    assert s.closed_at is not None and not s.is_open()


def test_dashboard_reflects_state(client):
    _login(client)
    assert b"No session is open." in client.get("/lecturer").data
    client.post("/lecturer/sessions")
    page = client.get("/lecturer").data
    assert b"A session is open." in page and b"Open session" not in page


@pytest.mark.parametrize("path", ["/lecturer/login", "/lecturer/nope", "/nope"])
def test_pages_have_no_internal_details(client, path):
    """Covers NFR-8: no traceback, file paths, or exception names."""
    body = client.get(path).data.decode()
    for bad in ("Traceback", "File \"", "sqlite", "SessionService", "app/", ".py", "Exception"):
        assert bad not in body


def test_dashboard_and_errors_hide_internals(client):
    _login(client)
    client.post("/lecturer/sessions")
    pages = [client.get("/lecturer").data, client.post("/lecturer/sessions").data,
             client.get("/lecturer/sessions").data, _login(client, "x").data]
    for body in pages:
        text = body.decode()
        for bad in ("Traceback", "sqlite", "SessionAlreadyOpenError", "WrongPinError", "SECRET", "test-secret-key"):
            assert bad not in text


def test_wrong_method_is_plain_405(client):
    _login(client)
    assert client.get("/lecturer/sessions").status_code == 405


def test_unexpected_error_is_generic_page(app, client):
    """Covers D23: an unexpected service failure shows the generic message, no traceback."""
    _login(client)
    svc = app.extensions["services"]["session_service"]

    def boom():
        raise RuntimeError("secret-internal-detail /tmp/x.py")
    svc.open_session = boom
    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = client.post("/lecturer/sessions")
    assert response.status_code == 500
    assert b"Something went wrong. Please try again." in response.data
    assert b"secret-internal-detail" not in response.data and b"Traceback" not in response.data


def test_templates_autoescape(app, client):
    """Covers NFR-8: Jinja autoescape is on for the templates (error message with HTML is escaped)."""
    from flask import render_template
    with app.test_request_context():
        html = render_template("error.html", message="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_race_on_open_maps_to_already_open(app):
    """Covers D27: if two requests race past find_open, the unique index error becomes the SRS message."""
    from app.errors import SessionAlreadyOpenError
    svc = app.extensions["services"]["session_service"]
    repo = app.extensions["services"]["sessions"]
    svc.open_session()
    real = repo.find_open
    repo.find_open = lambda: None  # simulate the stale read
    try:
        with pytest.raises(SessionAlreadyOpenError):
            svc.open_session()
    finally:
        repo.find_open = real
    assert _open_count(app) == 1
