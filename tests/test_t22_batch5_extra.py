"""T22k/T22l extra checks: repositories on empty/filled DB, login page, photo link 200, theme.js edge cases.
Covers D31, D38. Node-based tests are skipped when node is missing."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.repositories.comments import CommentRepository
from app.repositories.sessions import SessionRepository
from tests.test_t22_batch5 import HARNESS, STATIC

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")
FORBIDDEN = ("allow", "network", "relay", "campus")


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def test_services_latest_and_count_on_empty_db(client):
    services = client.application.extensions["services"]
    assert services["session_service"].latest() is None
    assert services["comment_service"].count() == 0


def test_repositories_latest_and_count_with_several_rows(client):
    services = client.application.extensions["services"]
    sessions = services["session_service"]
    first = sessions.open_session()
    sessions.close_session()
    second = sessions.open_session()
    assert sessions.latest().id == second.id and second.id != first.id  # open one is latest
    sessions.close_session()
    third = sessions.open_session()
    assert sessions.latest().id == third.id
    for text in ("a", "b", "c"):
        services["comment_service"].post(text)
    assert services["comment_service"].count() == 3


def test_repository_classes_expose_latest_and_count():
    assert hasattr(SessionRepository, "latest") and hasattr(CommentRepository, "count")


def test_login_page_has_no_nav_and_no_theme_button(client):
    page = client.get("/lecturer/login").get_data(as_text=True)
    assert "<nav" not in page and "theme-toggle" not in page and "theme.js" not in page


def test_photo_link_after_close_returns_200(lecturer):
    sessions = lecturer.application.extensions["services"]["session_service"]
    session = sessions.open_session()
    lecturer.post("/lecturer/sessions/close")
    page = lecturer.get("/lecturer").get_data(as_text=True)
    href = re.search(r'href="(/lecturer/sessions/\d+/photo)"', page).group(1)
    assert href == f"/lecturer/sessions/{session.id}/photo"
    assert lecturer.get(href).status_code == 200


def test_poll_question_with_quotes_and_script_is_escaped(lecturer):
    polls = lecturer.application.extensions["services"]["poll_service"]
    polls.create('"><script>alert(1)</script>?', ["a", "b"])
    page = lecturer.get("/lecturer").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_lecturer_subpages_have_theme_button_and_no_forbidden_words(lecturer):
    for path in ("/lecturer/polls", "/lecturer/comments", "/lecturer/video"):
        page = lecturer.get(path).get_data(as_text=True)
        assert "theme-toggle" in page and "theme.js" in page, path
        assert not [w for w in FORBIDDEN if w in page.lower()], path


def test_student_pages_and_projector_have_no_theme_script(lecturer):
    for path in ("/", "/poll", "/comments", "/lecturer/projector"):
        page = lecturer.get(path).get_data(as_text=True)
        assert "theme.js" not in page and "theme-toggle" not in page, path
    assert 'data-theme="light"' in lecturer.get("/lecturer/projector").get_data(as_text=True)


def _run(initial=None, clicks=0, blocked=False):
    config = json.dumps({"initial": initial or {}, "clicks": clicks, "blocked": blocked})
    result = subprocess.run([NODE, "-e", HARNESS, str(STATIC / "theme.js"), config],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
@pytest.mark.parametrize("saved,expected", [("light", "light"), ("dark", "dark"), ("auto", None), ("", None), ("DARK", None)])
def test_saved_values_applied_and_no_data_theme_in_auto(saved, expected):
    seen = _run(initial={"theme": saved})
    assert seen[0]["theme"] == expected and seen[1]["theme"] == expected


@needs_node
def test_persistence_between_two_page_views():
    first = _run(clicks=2)
    assert first[-1]["stored"] == "dark"
    assert _run(initial={"theme": first[-1]["stored"]})[0]["theme"] == "dark"


@needs_node
def test_blocked_storage_full_cycle_returns_to_auto():
    seen = _run(blocked=True, clicks=3)
    assert [s["theme"] for s in seen[2:]] == ["light", "dark", None]


@needs_node
def test_label_follows_state():
    seen = _run(initial={"theme": "dark"}, clicks=1)
    assert seen[1]["label"] == "Dark" and seen[2]["label"] == "Auto"


def _relative_luminance(hex_color):
    """WCAG 2 relative luminance of a #RRGGBB colour (sRGB linearised, then weighted)."""
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground, background):
    """WCAG 2 contrast ratio (L_light + 0.05) / (L_dark + 0.05), between 1 and 21."""
    lighter, darker = sorted((_relative_luminance(foreground), _relative_luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _palette_tokens(selector):
    """Return the --cp-* tokens declared in the first CSS block opened by `selector` in app.css."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    start = css.index(selector)
    block = css[css.index("{", start) + 1:css.index("}", start)]
    return dict(re.findall(r"(--cp-[\w-]+):\s*(#[0-9A-Fa-f]{6})", block))


@pytest.mark.parametrize("selector", [":root:not([data-theme=dark])", "[data-theme=dark] {"])
def test_success_text_on_success_background_meets_wcag_aa(selector):
    """NFR-15 / D38: success text on its tinted background must reach 4.5:1 in light and dark palettes."""
    tokens = _palette_tokens(selector)
    assert _contrast_ratio(tokens["--cp-success"], tokens["--cp-success-bg"]) >= 4.5
