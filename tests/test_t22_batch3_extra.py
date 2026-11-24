"""T22e-T22g extra checks (D37, D38): check-in order, device marker, tab bar, error page, poll, comments counter."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.web.device import COOKIE_NAME

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
ALREADY = "You are already checked in for this class."
TAB_LINKS = ["/", "/poll", "/comments", "/review"]


def _state(app):
    svc = app.extensions["services"]["session_service"]
    svc.open_session()
    st = svc.projector_state()
    return st.check_in_url.split("test.example")[1], st.code


def _code(app):
    return app.extensions["services"]["session_service"].projector_state().code


def _sync(client, stored=()):
    return client.post("/device/sync", json={"stored": list(stored)})


def _text(client, path):
    return client.get(path).get_data(as_text=True)


# ---- check-in page --------------------------------------------------------------------------

def test_checkin_field_order_and_privacy_hint(app):
    """Covers T22e, D38: nickname < privacy hint < code < Confirm; first 'Confirm' is the submit button."""
    url, _ = _state(app)
    html = _text(app.test_client(), url)
    nick, hint, code = html.index('name="nickname"'), html.index("do not use your real name or ID"), html.index('name="code"')
    button = html.index('<button type="submit">Confirm</button>')
    assert nick < hint < code < button
    assert html.index("Confirm") == button + len('<button type="submit">')
    assert 'autofocus' in html[nick:hint] and 'required' in html[nick:hint]
    assert 'name="dt_stored"' in html and "device.js" in html
    assert "cp-tabbar" not in html


def test_checkin_has_no_nickname_field_when_already_named(app):
    """Covers T22e: without needs_nickname the code gets autofocus (render directly)."""
    from flask import render_template
    with app.test_request_context("/checkin"):
        html = render_template("checkin.html", needs_nickname=False)
    assert 'name="nickname"' not in html and "autofocus" in html and 'name="code"' in html


@pytest.mark.parametrize("nick", ["<script>alert(1)</script>", "שלום עולם", '"><img src=x onerror=1>'])
def test_nickname_escaped_on_success_page_without_tabbar(app, nick):
    """Covers T22e, D37: nickname escaped (Hebrew kept), bdi dir=auto, no tab bar on checked-in."""
    url, code = _state(app)
    phone = app.test_client()
    phone.get(url)
    html = phone.post("/checkin", data={"nickname": nick, "code": code}).get_data(as_text=True)
    assert "You are checked in" in html and 'dir="auto"' in html
    assert "<script>alert" not in html and "<img src=x" not in html
    assert "cp-tabbar" not in html and "device.js" in html
    if "שלום" in nick:
        assert nick in html


def test_cleared_cookie_with_stored_token_is_already_checked_in(app):
    """Covers D37 end to end: form carries dt_stored, device.js syncs, old identity wins after cookie clear."""
    url, code = _state(app)
    phone = app.test_client()
    page = _text(phone, url)
    assert 'name="dt_stored"' in page and "device.js" in page
    token = _sync(phone).get_json()["token"]
    assert phone.post("/checkin", data={"nickname": "Fox", "code": code}).status_code == 200
    phone.delete_cookie(COOKIE_NAME)
    phone.get(url)  # fresh cookie issued: new identity until device.js syncs
    assert _sync(phone, [token]).get_json()["token"] == token
    again = phone.get(url)
    assert again.status_code == 409 and ALREADY in again.get_data(as_text=True)
    refused = phone.post("/checkin", data={"nickname": "Fox2", "code": _code(app), "dt_stored": token})
    assert refused.status_code != 200 and "You are checked in" not in refused.get_data(as_text=True)


def test_vote_form_still_carries_device_marker(app):
    """Covers D37 on the vote form, and the refused double vote with a stored token."""
    polls = app.extensions["services"]["poll_service"]
    poll = polls.create("Q?", ["a", "b"])
    phone = app.test_client()
    html = _text(phone, "/poll")
    assert 'name="dt_stored"' in html and "device.js" in html
    token = _sync(phone).get_json()["token"]
    form = {"poll_id": poll.id, "option_id": poll.options[0].id}
    assert phone.post("/poll/vote", data=form).status_code == 302
    phone.delete_cookie(COOKIE_NAME)
    phone.get("/poll")
    _sync(phone, [token])
    again = phone.post("/poll/vote", data=form)
    assert again.status_code != 302 and b"You have already voted." in again.data


# ---- tab bar and menu -----------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/", "/poll", "/comments"])
def test_tab_bar_present_with_four_resolving_links(client, path):
    """Covers T22f: four links, each answers (no 404/500)."""
    html = _text(client, path)
    bar = re.search(r'<nav class="cp-tabbar".*?</nav>', html, re.S).group(0)
    assert re.findall(r'href="([^"]+)"', bar) == TAB_LINKS
    for link in TAB_LINKS:
        assert client.get(link).status_code == 200, link
    assert "<form" not in bar and "<script" not in bar


def test_menu_tile_hrefs(client):
    """Covers T22f: four tiles with exact hrefs, labels and hints."""
    html = _text(client, "/")
    assert re.findall(r'class="cp-tile" role="button" href="([^"]+)"', html) == ["/checkin", "/poll", "/comments", "/review"]
    for label in ("Check in", "Poll", "Comments", "Homework review", "Scan the QR code on the screen"):
        assert label in html


def test_menu_checkin_tile_gives_readable_error_without_session(client):
    r = client.get("/checkin")
    assert r.status_code in (400, 404, 409) and 'role="alert"' in r.get_data(as_text=True)


# ---- error page -----------------------------------------------------------------------------

def test_student_error_goes_back_to_menu_and_hides_internals(client):
    """Covers T22f: student error -> '/', no technical words."""
    r = client.get("/checkin")
    html = r.get_data(as_text=True)
    assert 'href="/"' in html and "Back to the menu" in html and 'href="/lecturer"' not in html.split("<main")[1]
    for bad in ("Error:", "Exception", ".py", "app/", "Traceback"):
        assert bad not in html, bad


def test_lecturer_error_goes_back_to_dashboard(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    html = _text(client, "/lecturer/nope")
    assert 'href="/lecturer"' in html and "Back to the dashboard" in html and "Back to the menu" not in html
    for bad in ("Error:", "Exception", ".py", "app/", "Traceback"):
        assert bad not in html, bad


def test_unexpected_exception_page_is_plain(app):
    """Covers T22f: a crash shows the generic message only."""
    @app.get("/boom")
    def boom():
        raise RuntimeError("secret app/internal.py detail")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    r = app.test_client().get("/boom")
    html = r.get_data(as_text=True)
    assert r.status_code == 500 and 'role="alert"' in html
    for bad in ("secret", "internal.py", "RuntimeError", "Traceback", "Error:", "Exception"):
        assert bad not in html, bad


# ---- poll and comments ----------------------------------------------------------------------

def test_poll_cards_escape_hebrew_and_markup(app):
    """Covers T22g: option cards, labels escaped, Hebrew intact, dir=auto on question and labels."""
    app.extensions["services"]["poll_service"].create("<script>q</script>", ["<b>x</b>", "כן"])
    html = _text(app.test_client(), "/poll")
    assert html.count('class="cp-option"') == 2 and html.count('<span dir="auto">') == 2
    assert '<h2 dir="auto">' in html
    assert "<script>q" not in html and "&lt;script&gt;q" in html and "<b>x" not in html and "&lt;b&gt;x" in html
    assert "כן" in html


def test_comments_banner_only_when_sent(client):
    assert "Thanks, sent anonymously." in _text(client, "/comments?sent=1")
    assert "Thanks, sent anonymously." not in _text(client, "/comments")
    r = client.post("/comments", data={"text": "hello"})
    assert r.status_code == 302 and "sent=1" in r.headers["Location"]


def test_student_templates_have_no_external_url():
    """Covers D38 / offline: no http(s) or protocol-relative URL in student templates."""
    for name in ("checkin", "checked_in", "message", "error", "_tabbar", "poll", "comments", "base"):
        src = (TEMPLATES / f"{name}.html").read_text()
        assert "http://" not in src and "https://" not in src and 'src="//' not in src and 'href="//' not in src, name


@pytest.mark.skipif(shutil.which("node") is None and not Path("/usr/local/bin/node").exists(), reason="node missing")
def test_comment_counter_script_runs_in_node(tmp_path):
    """Covers T22g: run the inline counter against a DOM stub; textContent only, counts characters."""
    src = (TEMPLATES / "comments.html").read_text()
    script = re.search(r"<script>(.*?)</script>", src, re.S).group(1)
    harness = tmp_path / "run.js"
    harness.write_text("""
const handlers = {};
const stubBox = { value: "", addEventListener: (e, f) => { handlers[e] = f; } };
const stubCounter = { textContent: "0 / 500" };
global.document = { getElementById: (id) => id === "comment-text" ? stubBox : stubCounter };
%s
const out = [];
for (const v of ["", "abc", "שלום", "x".repeat(500)]) { stubBox.value = v; handlers.input(); out.push(stubCounter.textContent); }
console.log(JSON.stringify(out));
""" % script)
    node = shutil.which("node") or "/usr/local/bin/node"
    res = subprocess.run([node, str(harness)], capture_output=True, text=True, timeout=20)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == '["0 / 500","3 / 500","4 / 500","500 / 500"]'
