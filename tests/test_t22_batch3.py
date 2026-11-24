"""T22e-T22g acceptance: student pages (check-in, menu, error page, poll, comments) after the D38 redesign."""
import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def _get(client, path):
    return client.get(path).get_data(as_text=True)


def _scan(app):
    """Open a session and scan its QR URL with a fresh phone; return (client, url, code)."""
    svc = app.extensions["services"]["session_service"]
    svc.open_session()
    state = svc.projector_state()
    return app.test_client(), state.check_in_url.split("test.example")[1], state.code


def test_checkin_order_and_attributes(app):
    """Covers T22e: nickname < code < Confirm, hint before the code, nothing named Confirm earlier."""
    client, url, _ = _scan(app)
    html = _get(client, url)
    nick, code, confirm = html.index('name="nickname"'), html.index('name="code"'), html.index("Confirm")
    assert nick < code < confirm
    assert html.index("do not use your real name or ID") < code
    assert "4-digit code" in html and 'name="dt_stored"' in html and "device.js" in html
    assert 'pattern="[0-9]{4}"' in html and 'inputmode="numeric"' in html and 'maxlength="4"' in html
    assert 'maxlength="30"' in html and 'dir="auto"' in html and 'enterkeyhint="go"' in html
    assert 'class="cp-tabbar"' not in html


def test_checkin_success_page(app):
    """Covers T22e: big check, escaped nickname in a bdi, no tab bar."""
    client, url, code = _scan(app)
    client.get(url)
    html = client.post("/checkin", data={"nickname": "<script>x</script>", "code": code},
                       follow_redirects=True).get_data(as_text=True)
    assert "You are checked in" in html and "cp-bigcheck" in html
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html
    assert "<bdi" in html and 'class="cp-tabbar"' not in html


def test_menu_tiles_and_tab_bar(client):
    html = _get(client, "/")
    assert "HereOrNot" in html and "Teaching tool" not in html
    for href in ('href="/poll"', 'href="/comments"', 'href="/checkin"', 'href="/review"'):
        assert href in html
    assert 'class="cp-tabbar"' in html


@pytest.mark.parametrize("path", ["/poll", "/comments"])
def test_tab_bar_on_poll_and_comments(client, path):
    html = _get(client, path)
    assert 'class="cp-tabbar"' in html and 'href="/review"' in html


def test_error_page_back_link_is_contextual(client, lecturer):
    bad = client.get("/does-not-exist").get_data(as_text=True)
    assert 'role="alert"' in bad and 'href="/"' in bad and "Back to the menu" in bad
    assert "Error:" not in bad and "Exception" not in bad and ".py" not in bad and "app/" not in bad
    lect = lecturer.get("/lecturer/does-not-exist").get_data(as_text=True)
    assert 'role="alert"' in lect and 'href="/lecturer"' in lect and "Back to the dashboard" in lect


def test_poll_cards_banner_and_safety(app, client):
    """Covers T22g: option cards, dir=auto, escaped labels, dt_stored, polling shape, banner after voting."""
    app.extensions["services"]["session_service"].open_session()
    app.extensions["services"]["poll_service"].create("Q <b>?", ["A<i>", "B"])
    html = _get(client, "/poll")
    assert html.count('class="cp-option"') == 2 and 'dir="auto"' in html and 'name="dt_stored"' in html
    assert "<i>" not in html and "&lt;i&gt;" in html and "&lt;b&gt;" in html
    assert "Thanks, your vote is counted." not in html
    src = (TEMPLATES / "poll.html").read_text()
    assert "innerHTML" not in src and "|safe" not in src
    period = int(re.search(r"setInterval\(async \(\) => \{.*?\}, (\d+)\);", src, re.S).group(1))
    assert 2000 <= period <= 3000


def test_poll_empty_state(client):
    html = _get(client, "/poll")
    assert "No poll is open right now." in html and "cp-empty" in html


def test_comments_banner_counter_and_no_sinks(client):
    html = _get(client, "/comments?sent=1")
    assert "Thanks, sent anonymously." in html and "cp-banner" in html
    assert 'maxlength="500"' in html and 'dir="auto"' in html and "0 / 500" in html
    src = (TEMPLATES / "comments.html").read_text()
    assert "innerHTML" not in src and "|safe" not in src and "textContent" in src
    assert "Thanks" not in _get(client, "/comments")


def test_student_templates_have_no_urls():
    for name in ("checkin", "checked_in", "message", "error", "_tabbar", "poll", "comments"):
        src = (TEMPLATES / f"{name}.html").read_text()
        assert not re.search(r"(https?:)?//[a-z0-9-]+\.[a-z]{2,}", src), name
