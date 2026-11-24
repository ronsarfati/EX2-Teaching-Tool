"""T22a/T22b batch 1 acceptance: every page renders in the new shell, nav links resolve, CSS sane, no stale name.
Covers D38 (visual identity), spec sections 1, 5 (T22a, T22b) and 5.1."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
OLD_NAME = "Class" + "Pulse"


@pytest.fixture
def open_session(app):
    return app.extensions["services"]["session_service"].open_session()


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def _scan_path(app):
    state = app.extensions["services"]["session_service"].projector_state()
    return state.check_in_url.split("test.example")[1]


# ---------- every page renders 200 with the shell ----------

def test_student_pages_render_with_shell(app, open_session):
    """Covers T22a: student menu, check-in after a scan, poll, comments, review, error page."""
    phone = app.test_client()
    pages = {"/": phone.get("/"), "/poll": phone.get("/poll"), "/comments": phone.get("/comments"),
             "/review": phone.get("/review"), "scan": phone.get(_scan_path(app))}
    for name, resp in pages.items():
        assert resp.status_code == 200, name
        html = resp.get_data(as_text=True)
        assert "app.css" in html and "HereOrNot" in html and "cp-header" in html, name
        assert OLD_NAME not in html, name
    assert 'name="code"' in pages["scan"].get_data(as_text=True)


def test_error_page_renders_with_shell(client):
    """Covers T22a: error page keeps role=alert, no 'Error:', no internals."""
    resp = client.post("/review", data={"url": "https://example.com/x/y"})
    html = resp.get_data(as_text=True)
    assert resp.status_code in (400, 503)
    assert 'role="alert"' in html and "app.css" in html and "Error:" not in html
    assert "Traceback" not in html and ".py" not in html


def test_checked_in_page_renders_with_shell(app, open_session):
    phone = app.test_client()
    phone.get(_scan_path(app))
    code = app.extensions["services"]["session_service"].projector_state().code
    resp = phone.post("/checkin", data={"nickname": "Fox", "code": code, "dt_stored": ""}, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200 and "You are checked in" in html and "app.css" in html


def test_poll_page_with_open_poll_renders(app, lecturer):
    lecturer.post("/lecturer/polls", data={"question": "Topic?", "option": ["Graphs", "Trees"]})
    resp = app.test_client().get("/poll")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200 and "Topic?" in html and "app.css" in html


LECTURER_GET = ["/lecturer", "/lecturer/polls", "/lecturer/comments", "/lecturer/video", "/lecturer/peers",
                "/lecturer/export.xlsx", "/lecturer/export/checkins.csv", "/lecturer/export/summary.csv"]


@pytest.mark.parametrize("path", LECTURER_GET)
def test_lecturer_pages_200_closed_and_open(app, lecturer, path):
    """Covers T22b: every lecturer page renders without and with an open session."""
    assert lecturer.get(path).status_code == 200
    lecturer.post("/lecturer/sessions")
    resp = lecturer.get(path)
    assert resp.status_code == 200
    if not path.startswith("/lecturer/export"):
        html = resp.get_data(as_text=True)
        assert "app.css" in html and "<nav" in html and OLD_NAME not in html


def test_projector_and_photo_pages_render(lecturer):
    lecturer.post("/lecturer/sessions")
    proj = lecturer.get("/lecturer/projector")
    html = proj.get_data(as_text=True)
    assert proj.status_code == 200 and 'id="qr"' in html and 'id="code"' in html
    assert "http" not in html and "cdn" not in html and "xmlns" not in html
    assert lecturer.get("/lecturer/sessions/1/photo").status_code == 200


def test_login_page_has_shell_and_no_nav(client):
    resp = client.get("/lecturer/login")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200 and 'name="pin"' in html and "HereOrNot" in html and "<nav" not in html


def test_lecturer_pages_redirect_to_login_without_pin(client):
    for path in ("/lecturer", "/lecturer/polls", "/lecturer/projector"):
        r = client.get(path)
        assert r.status_code == 302 and "/lecturer/login" in r.headers["Location"]


# ---------- lecturer nav links resolve ----------

def test_every_nav_link_resolves(lecturer):
    """Covers T22b: no nav link 404s (including target=projector and /review)."""
    lecturer.post("/lecturer/sessions")
    html = lecturer.get("/lecturer").get_data(as_text=True)
    nav = re.search(r"<nav.*?</nav>", html, re.S).group(0)
    hrefs = re.findall(r'href="([^"]+)"', nav)
    assert len(hrefs) == 6 and len(set(hrefs)) == 6
    for href in hrefs:
        assert href.startswith("/") and not href.startswith("//")
        assert lecturer.get(href).status_code == 200, href


def test_nav_identical_on_every_lecturer_page(lecturer):
    navs = {re.search(r"<nav.*?</nav>", lecturer.get(p).get_data(as_text=True), re.S).group(0)
            for p in ("/lecturer", "/lecturer/polls", "/lecturer/comments", "/lecturer/video", "/lecturer/peers")}
    assert len(navs) == 1


def test_dashboard_words_still_hold(lecturer):
    closed = lecturer.get("/lecturer").get_data(as_text=True)
    assert "No session is open." in closed and "Open session" in closed
    lecturer.post("/lecturer/sessions")
    opened = lecturer.get("/lecturer").get_data(as_text=True).lower()
    assert "a session is open." in opened and "open session" not in opened
    for bad in ("allow", "network", "relay", "campus"):
        assert bad not in opened


# ---------- repository-wide hygiene ----------

def _text_files():
    for base in (APP, ROOT / "tests", ROOT / "scripts"):
        for p in base.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".html", ".js", ".css", ".svg",
                                                                              ".command", ".sql", ".md"}:
                yield p


def test_no_old_name_anywhere_in_repo():
    needle = "class" + "pulse"
    hits = [str(p) for p in list(_text_files()) + list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*.md"))
            if needle in p.read_text(errors="ignore").lower()]
    assert hits == []


def test_no_external_url_in_templates_and_static():
    """Covers D38 'no CDN': only favicon.svg xmlns, the review placeholder and the vendored Pico banner may match."""
    allowed = {"favicon.svg", "pico.min.css", "review.html"}
    for p in list((APP / "templates").rglob("*")) + list((APP / "static").rglob("*")):
        if p.is_file() and p.name not in allowed:
            text = p.read_text(errors="ignore")
            assert not re.search(r"https?://|(?<!:)//[a-z]", text.replace("</", "")), p
    assert re.findall(r"https?://[^\"' ]+", (APP / "templates" / "review.html").read_text()) == [
        "https://github.com/owner/repository"]
    assert 'xmlns="http://www.w3.org/2000/svg"' in (APP / "static" / "favicon.svg").read_text()


def test_templates_have_no_xmlns_or_inline_script_in_shell():
    for name in ("base.html", "lecturer_base.html", "_icons.html"):
        src = (APP / "templates" / name).read_text()
        assert 'xmlns="' not in src, name
    base = (APP / "templates" / "base.html").read_text()
    assert "<script" not in base and "<form" not in base


def test_forbidden_words_absent_from_app_sources():
    banned = ["campus", "relay", "allow-list", "allow_list", "allowlist", "remote_addr", "x-forwarded-for",
              "client_ip", "ipaddress", "networkpolicy", "network_origin", "3-digit", "three-digit"]
    for p in APP.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".html", ".js", ".sql"} and "__pycache__" not in p.parts:
            low = p.read_text().lower()
            for w in banned:
                assert w not in low, (p, w)


# ---------- app.css ----------

@pytest.fixture
def css():
    return (APP / "static" / "app.css").read_text()


def _strip_comments(s):
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


def test_css_braces_and_parens_balanced(css):
    body = _strip_comments(css)
    assert body.count("{") == body.count("}") and body.count("{") > 20
    assert body.count("(") == body.count(")")
    depth = 0
    for ch in body:
        depth += (ch == "{") - (ch == "}")
        assert depth >= 0
    assert css.count("/*") == css.count("*/")


def test_css_dark_mode_selectors_and_tokens(css):
    assert "@media only screen and (prefers-color-scheme: dark)" in css
    assert ":root:not([data-theme])" in css and "[data-theme=dark]" in css and "[data-theme=light]" in css
    light = {"--cp-bg": "#F7F8FC", "--cp-primary": "#3B4FD8", "--cp-accent": "#FF8A3D", "--cp-error": "#C2272D"}
    dark = {"--cp-bg": "#0F1220", "--cp-primary": "#8C9BFF", "--cp-accent": "#FF9F5A", "--cp-error": "#FF7A7F"}
    for k, v in {**light, **dark}.items():
        assert f"{k}: {v}" in css, (k, v)
    for pico in ("--pico-primary", "--pico-background-color", "--pico-color", "--pico-card-background-color",
                 "--pico-border-radius", "--pico-font-family-sans-serif"):
        assert pico in css, pico


def test_css_every_used_cp_variable_is_defined(css):
    used = set(re.findall(r"var\((--cp-[a-z0-9-]+)", css))
    defined = set(re.findall(r"(--cp-[a-z0-9-]+)\s*:", css))
    assert used - defined == set()


def test_css_accessibility_rules(css):
    assert "prefers-reduced-motion: reduce" in css
    assert "outline: 3px solid var(--cp-accent)" in css.replace("  ", " ")
    assert re.search(r"min-height:\s*48px", css) and "56px" in css
    assert ".cp-danger" in css and ".cp-chip" in css and ".cp-banner" in css and ".cp-stat" in css
    assert "@import" not in css and "url(" not in css


def test_css_uses_system_fonts_only(css):
    assert "system-ui" in css and "Noto Sans Hebrew" in css and "@font-face" not in css


def test_stylesheet_served_with_css_mimetype(client):
    r = client.get("/static/app.css")
    assert r.status_code == 200 and r.mimetype == "text/css"


# ---------- icons / favicon ----------

def test_icon_macro_covers_the_nav_icons():
    src = (APP / "templates" / "_icons.html").read_text()
    for name in ("users", "qr", "bar-chart", "message", "film", "git-branch", "camera", "check", "download", "alert"):
        assert f'"{name}"' in src, name


def test_favicon_is_valid_svg_and_has_no_script():
    import xml.etree.ElementTree as ET
    root = ET.parse(APP / "static" / "favicon.svg").getroot()
    assert root.tag.endswith("svg")
    assert "<script" not in (APP / "static" / "favicon.svg").read_text().lower()


def test_theme_color_metas_and_color_scheme(client):
    html = client.get("/").get_data(as_text=True)
    assert html.count('name="theme-color"') == 2 and 'content="light dark"' in html
    assert 'href="/static/favicon.svg"' in html and "//static" not in html
