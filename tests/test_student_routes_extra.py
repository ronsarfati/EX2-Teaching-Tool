"""Extra end-to-end tests for the student check-in pages (T8). Covers FR-1.2, FR-1.6-FR-1.12, NFR-1, UC-2, UC-3, SRS section 5."""
import re
from pathlib import Path

import pytest

CAMPUS = "192.0.2.10"


@pytest.fixture
def services(app):
    s = app.extensions["services"]
    s["settings"].replace_values("campus_range", ["192.0.2.0/24"])
    return s


@pytest.fixture
def session(services):
    return services["session_service"].open_session()


class Phone:
    """One browser: own cookie jar, fixed source address."""

    def __init__(self, app, ip=CAMPUS, headers=None):
        self.app = app
        self.client = app.test_client()
        self.kw = {"environ_base": {"REMOTE_ADDR": ip}, "headers": headers or {}}
        self.svc = app.extensions["services"]["session_service"]

    def url(self):
        return self.svc.projector_state().check_in_url.split("test.example")[1]

    def code(self):
        return self.svc.projector_state().code

    def wrong(self):
        return f"{(int(self.code()) + 1) % 1000:03d}"

    def scan(self, url=None):
        return self.client.get(url or self.url(), **self.kw)

    def post(self, nickname="Fox", code=None):
        data = {"code": self.code() if code is None else code}
        if nickname is not None:
            data["nickname"] = nickname
        return self.client.post("/checkin", data=data, **self.kw)


def text(response):
    return response.get_data(as_text=True)


# ---- HTML structure (UC-2, FR-1.7) ----

def test_field_order_and_attributes(app, session):
    """Covers UC-2 first visit: nickname, then code, then Confirm; mobile keypad."""
    html = text(Phone(app).scan())
    i_nick, i_code, i_btn = html.index('name="nickname"'), html.index('name="code"'), html.index("Confirm")
    assert i_nick < i_code < i_btn
    assert html.index("do not use your real name or ID") < i_code
    nick_tag = re.search(r"<input[^>]*name=\"nickname\"[^>]*>", html).group(0)
    code_tag = re.search(r"<input[^>]*name=\"code\"[^>]*>", html).group(0)
    assert 'maxlength="30"' in nick_tag
    assert 'inputmode="numeric"' in code_tag and 'maxlength="3"' in code_tag


def test_first_visit_then_returning_next_session(app, session, services):
    """Covers UC-2, UC-3: nickname asked once, reused at the next class."""
    p = Phone(app)
    p.scan()
    first = p.post("Fox")
    assert first.status_code == 200 and "Fox" in text(first)
    services["session_service"].close_session()
    services["session_service"].open_session()
    html = text(p.scan())
    assert 'name="nickname"' not in html
    assert html.index('name="code"') < html.index("Confirm")
    second = p.post(nickname=None)
    assert second.status_code == 200 and "Fox" in text(second)


def test_returning_device_ignores_posted_nickname(app, session, services):
    """Covers FR-1.7: stored nickname wins."""
    p = Phone(app)
    p.scan()
    p.post("Fox")
    services["session_service"].close_session()
    services["session_service"].open_session()
    p.scan()
    response = p.post("Other")
    assert "Fox" in text(response) and "Other" not in text(response)


def test_one_checkin_row_after_success(app, session):
    """Covers FR-1.6: exactly one check-in stored."""
    p = Phone(app)
    p.scan()
    p.post("Fox")
    n = app.extensions["services"]["db"].conn().execute("SELECT COUNT(*) FROM check_in").fetchone()[0]
    assert n == 1


# ---- error messages reachable through HTTP (SRS section 5) ----

def test_err_wrong_code(app, session):
    p = Phone(app)
    p.scan()
    r = p.post("Fox", p.wrong())
    assert r.status_code == 400 and "Wrong code. Type the code shown under the QR now." in text(r)


def test_err_empty_nickname(app, session):
    p = Phone(app)
    p.scan()
    r = p.post("   ")
    assert r.status_code == 400 and "Please choose a nickname (not your real name or ID)." in text(r)


def test_err_missing_nickname_field(app, session):
    p = Phone(app)
    p.scan()
    assert "Please choose a nickname" in text(p.post(nickname=None))


def test_nickname_length_boundary(app, session):
    """Covers FR-1.7: 30 chars accepted, 31 refused."""
    p = Phone(app)
    p.scan()
    assert "Please choose a nickname" in text(p.post("a" * 31))
    ok = p.post("a" * 30)
    assert ok.status_code == 200 and "a" * 30 in text(ok)


def test_window_boundary_60s_ok_60_001_expired(app, session, clock):
    """Covers FR-1.8: 60 s inclusive, 60.001 s expired."""
    p = Phone(app)
    p.scan()
    clock.advance(60)
    assert p.post("Fox").status_code == 200
    q = Phone(app)
    q.scan()
    clock.advance(60.001)
    r = q.post("Fox")
    assert r.status_code == 400 and "Your check-in time ran out. Scan the QR code again." in text(r)


def test_attempt_limit_5_then_6th_refused(app, session):
    """Covers FR-1.9: 5 wrong tries answered 'wrong code', the 6th refused with 429."""
    p = Phone(app)
    p.scan()
    for _ in range(5):
        assert "Wrong code" in text(p.post("Fox", p.wrong()))
    r = p.post("Fox", p.code())
    assert r.status_code == 429 and "Too many tries. Scan the QR code again." in text(r)


def test_empty_nickname_not_counted_as_attempt(app, session):
    """Covers D31."""
    p = Phone(app)
    p.scan()
    for _ in range(6):
        p.post("", p.wrong())
    assert p.post("Fox").status_code == 200


def test_qr_age_boundary(app, session, clock):
    """Covers FR-1.3: QR valid at 15 s, expired at 15.001 s."""
    p = Phone(app)
    url = p.url()
    clock.advance(15)
    assert p.scan(url).status_code == 200
    q = Phone(app)
    clock.advance(0.001)
    r = q.scan(url)
    assert r.status_code == 400 and "This QR code has expired. Scan a fresh one." in text(r)


def test_tampered_token(app, session):
    p = Phone(app)
    url = p.url()
    tampered = url[:-1] + ("A" if url[-1] != "A" else "B")
    r = p.scan(tampered)
    assert r.status_code == 400 and "QR code" in text(r)
    assert "Traceback" not in text(r)


def test_session_closed(app, session, services):
    p = Phone(app)
    url = p.url()
    services["session_service"].close_session()
    r = p.scan(url)
    assert r.status_code == 409 and "Attendance for this class is closed." in text(r)


def test_session_closed_between_scan_and_confirm(app, session, services):
    p = Phone(app)
    p.scan()
    services["session_service"].close_session()
    r = p.post("Fox", "123")
    assert r.status_code == 409 and "Attendance for this class is closed." in text(r)


def test_off_campus_is_accepted_and_labelled(app, session):
    p = Phone(app, ip="198.51.100.7")
    assert p.scan().status_code == 200  # D32: no refusal
    assert p.post().status_code == 200
    rows = app.extensions["services"]["check_ins"].list_for_session(session.id)
    assert [c.network_origin.value for c in rows] == ["off_campus"]


def test_malformed_address_refused_with_message(app, session):
    r = Phone(app, ip="127.0.0.1", headers={"CF-Connecting-IP": "not-an-ip"}).scan()
    assert r.status_code == 403
    assert "Check-in is not available right now. Ask the lecturer." in text(r)


def test_off_campus_post_without_window(app, session):
    assert Phone(app, ip="198.51.100.7").post("Fox", "123").status_code == 400  # no scan first: no window


def test_already_checked_in_get_and_post(app, session):
    p = Phone(app)
    p.scan()
    p.post("Fox")
    r = p.scan()
    assert r.status_code == 409 and "You are already checked in for this class." in text(r)
    # Same phone, window gone: posting again cannot create a second check-in.
    assert p.post("Fox").status_code == 400


def test_checkin_get_without_token(app):
    p = Phone(app)
    r = p.client.get("/checkin", **p.kw)
    assert r.status_code == 404 and "There is no attendance check-in right now." in text(r)


def test_checkin_get_without_token_open_session(app, session):
    p = Phone(app)
    r = p.client.get("/checkin", **p.kw)
    assert r.status_code == 400 and "Scan the QR code on the projector." in text(r)


# ---- client address (FR-1.2) ----

@pytest.mark.parametrize("peer,expected", [("127.0.0.1", 200), ("::1", 200), ("198.51.100.7", 200), ("10.0.0.5", 200)])
def test_cf_header_only_from_loopback(app, session, peer, expected):
    p = Phone(app, ip=peer, headers={"CF-Connecting-IP": CAMPUS})
    assert p.scan().status_code == expected


def test_loopback_without_header_is_off_campus(app, session):
    p = Phone(app, ip="127.0.0.1")
    assert p.scan().status_code == 200
    p.post()
    rows = app.extensions["services"]["check_ins"].list_for_session(session.id)
    assert rows[0].network_origin.value == "off_campus"


def test_loopback_with_off_campus_header(app, session):
    p = Phone(app, ip="127.0.0.1", headers={"CF-Connecting-IP": "198.51.100.7"})
    assert p.scan().status_code == 200


# ---- cookie and privacy (D6, NFR-1) ----

def test_cookie_flags_and_single_set(app, session):
    p = Phone(app)
    r = p.scan()
    cookies = r.headers.getlist("Set-Cookie")
    assert len(cookies) == 1
    c = cookies[0]
    assert c.startswith("dt=") and "HttpOnly" in c and "SameSite=Lax" in c and "Max-Age=31536000" in c


def test_cookie_token_is_random_per_device(app, session):
    a = Phone(app).scan().headers["Set-Cookie"].split(";")[0]
    b = Phone(app).scan().headers["Set-Cookie"].split(";")[0]
    assert a != b


def test_no_internals_in_any_body(app, session, services, clock):
    """Covers NFR-1: no IP, token, class names or traceback in pages."""
    p = Phone(app)
    url = p.url()
    token = url.rsplit("/", 1)[1]
    bodies = [text(p.scan())]
    bodies.append(text(p.post("Fox", p.wrong())))
    bodies.append(text(p.client.get("/c/garbage", **p.kw)))
    bodies.append(text(Phone(app, ip="198.51.100.7").scan()))
    bodies.append(text(p.post("Fox")))
    bodies.append(text(p.scan()))
    clock.advance(30)
    bodies.append(text(Phone(app).scan(url)))
    for body in bodies:
        for bad in (CAMPUS, "198.51.100.7", token, "Traceback", "Error:", "Exception", "app/", ".py", "sqlite", "File \""):
            assert bad not in body, bad


def test_nickname_html_escaped(app, session):
    p = Phone(app)
    p.scan()
    r = p.post("<script>x</script>")
    body = text(r)
    assert "<script>x" not in body and "&lt;script&gt;" in body


def test_templates_have_no_external_urls():
    """Covers NFR-1: nothing loaded from third-party hosts."""
    for name in ("base.html", "checkin.html", "checked_in.html", "message.html", "error.html"):
        content = (Path(__file__).resolve().parents[1] / "app" / "templates" / name).read_text()
        assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}", content, re.I), name
