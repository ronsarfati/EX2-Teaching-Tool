"""T22c/T22d acceptance: dashboard reorganisation and projector layout (D38)."""
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
FORBIDDEN = ("allow", "network", "relay", "campus", "secret")


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def _page(client, path="/lecturer"):
    return client.get(path).get_data(as_text=True)


def test_dashboard_closed_state(lecturer):
    """Covers T22c: closed chip, Open session, no Projector link, no live widgets."""
    html = _page(lecturer)
    assert "No session is open." in html and "Open session" in html and "Closed" in html
    assert "/lecturer/projector" not in html.split("</nav>")[1]
    assert 'id="n"' not in html and "poll_json.js" not in html
    for word in FORBIDDEN:
        assert word not in html.lower()


def test_dashboard_open_state(lecturer):
    """Covers T22c: Live chip, projector link, confirmed close, stat tiles, no 'Open session'."""
    lecturer.post("/lecturer/sessions")
    html = _page(lecturer)
    body = html.split("</nav>")[1]
    assert "A session is open." in html and 'data-state="live"' in html
    assert "Open session" not in html and "Close session" in html
    assert 'href="/lecturer/projector"' in body and 'target="projector"' in body
    assert "confirm(" in html
    for ident in ("n", "d", "status", "attendance-rows", "attendance-error"):
        assert f'id="{ident}"' in html
    assert "In class now" in html and "After class" in html
    for word in FORBIDDEN:
        assert word not in html.lower()


def test_dashboard_after_class_links(lecturer):
    html = _page(lecturer)
    for href in ("/lecturer/export.xlsx", "/lecturer/export/checkins.csv", "/lecturer/export/summary.csv",
                 "/lecturer/comments", "/lecturer/polls", "/lecturer/video", "/review", "/lecturer/peers"):
        assert f'href="{href}"' in html, href


def test_poll_json_sets_state_dir_and_empty_row():
    js = (STATIC / "poll_json.js").read_text()
    assert "statusEl.dataset.state" in js and 'td.dir = "auto"' in js
    assert "Nobody has checked in yet" in js
    assert "POLL_MS = 2500" in js and "setInterval(poll, POLL_MS)" in js
    code = re.sub(r"//.*", "", js)  # the header comment names innerHTML to forbid it
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "origin"):
        assert sink not in code


def test_projector_layout(lecturer):
    """Covers T22d: forced light theme, steps 1-2-3, links, ids kept, no URL."""
    lecturer.post("/lecturer/sessions")
    html = _page(lecturer, "/lecturer/projector")
    assert 'data-theme="light"' in html and 'id="qr"' in html and 'id="code"' in html
    assert "1. Scan the QR" in html and "2. Type this code" in html and "3. Tap Confirm" in html
    assert 'href="/lecturer"' in html and "Full screen" in html and 'id="projector-error"' in html
    assert "http" not in html and "cdn" not in html.lower()
    assert "//" not in re.sub(r"<!--.*?-->", "", html, flags=re.S).replace("</", "")
    assert "<nav" not in html and "Polls" not in html  # no lecturer nav on the projector


def test_projector_js_error_goes_to_its_own_element():
    """A failed poll must not overwrite #waiting, so it reads 'No session is open.' again after a success."""
    js = (STATIC / "projector.js").read_text()
    assert "POLL_MS = 1000" in js and "setInterval(poll, POLL_MS)" in js
    catch = js.split("catch (error)")[1].split("fullscreenLink")[0]
    assert "errorEl.hidden = false" in catch and "waitingEl" not in catch
    assert "errorEl.hidden = true" in js.split("catch (error)")[0]
    assert "http://" not in js and "https://" not in js
