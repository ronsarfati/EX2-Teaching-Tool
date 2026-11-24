"""T22k/T22l: dashboard summary data and the manual theme toggle (theme.js run under node against a DOM stub)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_t18e_video_routes import login, make_client, post_video
from tests.fakes import DeferredJobRunner

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")
FORBIDDEN = ("allow", "network", "relay", "campus")


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def _services(client):
    return client.application.extensions["services"]


def _page(client):
    return client.get("/lecturer").get_data(as_text=True)


# ---- T22k ----

def test_dashboard_without_data_shows_no_summary(lecturer):
    page = _page(lecturer)
    assert "0 received" in page and "Latest (" not in page and "See progress" not in page
    assert "last session" not in page


def test_dashboard_shows_latest_poll_and_comment_count(lecturer):
    services = _services(lecturer)
    services["poll_service"].create("Tea <b>or</b> coffee?", ["Tea", "Coffee"])
    services["comment_service"].post("hello")
    services["comment_service"].post("shalom")
    page = _page(lecturer)
    assert "Latest (open): Tea &lt;b&gt;or&lt;/b&gt; coffee?" in page and "<b>or</b>" not in page
    assert "2 received" in page
    services["poll_service"].close(services["poll_service"].latest().id)
    assert "Latest (closed)" in _page(lecturer)


def test_photo_link_survives_closing_the_session(lecturer):
    services = _services(lecturer)
    session = services["session_service"].open_session()
    page = _page(lecturer)
    assert f"/lecturer/sessions/{session.id}/photo" in page and "Open session" not in page
    lecturer.post("/lecturer/sessions/close")
    page = _page(lecturer)
    assert f"/lecturer/sessions/{session.id}/photo" in page and "last session" in page
    assert "Open session" in page and "A session is open." not in page


def test_photo_link_targets_the_newest_session(lecturer):
    sessions = _services(lecturer)["session_service"]
    sessions.open_session()
    sessions.close_session()
    second = sessions.open_session()
    sessions.close_session()
    assert f"/lecturer/sessions/{second.id}/photo" in _page(lecturer)


def test_dashboard_shows_the_active_video_job_with_its_link(config, clock):
    client, _ = make_client(config, clock, runner=DeferredJobRunner())
    login(client)
    post_video(client)
    page = _page(client)
    assert "Waiting to start" in page and 'href="/lecturer/video/jobs/1"' in page


def test_finished_video_job_is_not_shown_as_active(config, clock):
    client, _ = make_client(config, clock)
    login(client)
    post_video(client)
    assert "See progress" not in _page(client)


def test_dashboard_still_avoids_forbidden_words(lecturer):
    services = _services(lecturer)
    services["poll_service"].create("Q?", ["a", "b"])
    services["session_service"].open_session()
    for state in ("open", "closed"):
        page = _page(lecturer).lower()
        assert not [word for word in FORBIDDEN if word in page], state
        lecturer.post("/lecturer/sessions/close")


# ---- T22l ----

def test_theme_button_is_a_button_in_the_lecturer_nav_only(lecturer):
    page = _page(lecturer)
    assert '<button type="button" id="theme-toggle"' in page
    assert page.index("theme.js") < page.index("</head>")
    nav = page[page.index("<nav"):page.index("</nav>")]
    assert "<form" not in nav
    projector = lecturer.get("/lecturer/projector").get_data(as_text=True)
    assert "theme.js" not in projector and "theme-toggle" not in projector and 'data-theme="light"' in projector
    assert "theme.js" not in lecturer.get("/").get_data(as_text=True)


def test_theme_js_is_served_offline_and_css_keeps_data_theme_selectors():
    source = (STATIC / "theme.js").read_text()
    assert "http" not in source and "innerHTML" not in source and "//" not in source.replace("*/", "")
    css = (STATIC / "app.css").read_text()
    assert "[data-theme=dark]" in css and "[data-theme=light]" in css and ":root:not([data-theme])" in css


def test_theme_js_is_served(lecturer):
    assert lecturer.get("/static/theme.js").status_code == 200


HARNESS = r"""
const fs = require("fs");
const config = JSON.parse(process.argv[2]);
const attrs = {};
const listeners = {};
const button = {textContent: "", attrs: {}, handlers: [],
  setAttribute(k, v) { this.attrs[k] = v; }, addEventListener(t, f) { this.handlers.push(f); }};
const store = Object.assign({}, config.initial);
const localStorage = config.blocked
  ? {getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }}
  : {getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; }};
global.window = {localStorage};
global.document = {
  documentElement: {setAttribute(k, v) { attrs[k] = v; }, removeAttribute(k) { delete attrs[k]; }},
  getElementById: (id) => (id === "theme-toggle" ? button : null),
  addEventListener(t, f) { listeners[t] = f; },
};
eval(fs.readFileSync(process.argv[1], "utf8"));
const seen = [{theme: attrs["data-theme"] || null, label: button.textContent}];
if (listeners.DOMContentLoaded) listeners.DOMContentLoaded();
seen.push({theme: attrs["data-theme"] || null, label: button.textContent});
for (let i = 0; i < config.clicks; i++) {
  button.handlers.forEach((f) => f());
  seen.push({theme: attrs["data-theme"] || null, label: button.textContent, stored: store.theme || null});
}
console.log(JSON.stringify(seen));
"""


def _run(initial=None, clicks=0, blocked=False):
    config = json.dumps({"initial": initial or {}, "clicks": clicks, "blocked": blocked})
    result = subprocess.run([NODE, "-e", HARNESS, str(STATIC / "theme.js"), config],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
def test_theme_cycles_auto_light_dark_and_back():
    seen = _run(clicks=4)
    assert [s["theme"] for s in seen[1:]] == [None, "light", "dark", None, "light"]
    assert [s["label"] for s in seen[2:]] == ["Light", "Dark", "Auto", "Light"]
    assert seen[2]["stored"] == "light" and seen[4]["stored"] == "auto"


@needs_node
def test_saved_theme_is_applied_before_the_page_is_ready():
    assert _run(initial={"theme": "dark"})[0]["theme"] == "dark"


@needs_node
def test_unknown_saved_value_falls_back_to_auto():
    assert _run(initial={"theme": "purple"})[0]["theme"] is None


@needs_node
def test_blocked_storage_does_not_break_the_toggle():
    seen = _run(blocked=True, clicks=2)
    assert seen[0]["theme"] is None
    assert [s["theme"] for s in seen[2:]] == ["light", "dark"]
