"""T22a/T22b: design shell, stylesheet, lecturer navigation and login page (D38)."""
import re

import pytest

LECTURER_PAGES = ["/lecturer", "/lecturer/polls", "/lecturer/comments", "/lecturer/video", "/lecturer/peers"]


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


@pytest.mark.parametrize("path", ["/static/app.css", "/static/favicon.svg", "/static/pico.min.css"])
def test_static_assets_served(client, path):
    assert client.get(path).status_code == 200


def test_stylesheet_loaded_after_pico(client):
    html = client.get("/lecturer/login").get_data(as_text=True)
    assert html.index("pico.min.css") < html.index("app.css")
    assert 'rel="icon"' in html and 'name="color-scheme"' in html


@pytest.mark.parametrize("path", ["/", "/lecturer/login", "/poll", "/comments"])
def test_shell_has_no_url_form_or_namespace(client, path):
    html = client.get(path).get_data(as_text=True)
    assert "http" not in html and "xmlns" not in html
    assert "<form" not in html.split("<main")[0]
    assert "HereOrNot" in html


def test_no_old_app_name_in_repo():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    needle = "class" + "pulse"
    hits = [p for p in list((root / "app").rglob("*")) + list((root / "tests").rglob("*.py"))
            if p.is_file() and p.suffix in {".py", ".html", ".js", ".css", ".svg"}
            and needle in p.read_text().lower()]
    assert hits == []


@pytest.mark.parametrize("path", LECTURER_PAGES)
def test_lecturer_nav_on_lecturer_pages(lecturer, path):
    html = lecturer.get(path).get_data(as_text=True)
    nav = re.search(r"<nav.*?</nav>", html, re.S).group(0)
    assert 'target="projector"' in nav and 'href="/lecturer/projector"' in nav
    for href in ("/lecturer", "/lecturer/polls", "/lecturer/comments", "/lecturer/video", "/review"):
        assert f'href="{href}"' in nav
    assert "<form" not in nav


def test_lecturer_nav_absent_from_projector_and_login(lecturer, client):
    assert "<nav" not in lecturer.get("/lecturer/projector").get_data(as_text=True)
    assert "<nav" not in client.application.test_client().get("/lecturer/login").get_data(as_text=True)


def test_login_restyled_keeps_pin_field_and_alert(client):
    page = client.get("/lecturer/login").get_data(as_text=True)
    assert 'name="pin"' in page and "Log in" in page
    wrong = client.post("/lecturer/login", data={"pin": "0000"})
    html = wrong.get_data(as_text=True)
    assert "Wrong PIN." in html and 'role="alert"' in html and "0000" not in html
