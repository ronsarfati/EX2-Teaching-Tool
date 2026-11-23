"""Extra T6 tests: QR content, slot edges, reopen, 401 without leak, page and JS (FR-1.5, FR-1.8, FR-1.13, D30, D31)."""
import base64
import re
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.adapters.qr import qr_png_data_uri
from app.services.credentials import RotatingCredentials

T0 = 1_000_000.0  # multiple of 10 and 5: start of a QR slot and a code slot


@pytest.fixture
def logged(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def png_bytes(uri: str) -> bytes:
    assert uri.startswith("data:image/png;base64,")
    return base64.b64decode(uri.split(",", 1)[1])


def decode_qr(uri: str) -> str:
    image = cv2.imdecode(np.frombuffer(png_bytes(uri), np.uint8), cv2.IMREAD_COLOR)
    return cv2.QRCodeDetector().detectAndDecode(image)[0]


def state(logged):
    return logged.get("/api/projector").get_json()


def token_of(uri: str) -> str:
    url = decode_qr(uri)
    prefix = "https://test.example/c/"
    assert url.startswith(prefix)
    return url[len(prefix):]


def open_id(app) -> int:
    return app.extensions["services"]["sessions"].find_open().id


def test_qr_adapter_returns_png_data_uri():
    """Covers FR-1.5: PNG header and exact round trip of arbitrary text."""
    uri = qr_png_data_uri("hello-123")
    assert png_bytes(uri)[:8] == b"\x89PNG\r\n\x1a\n"
    assert decode_qr(uri) == "hello-123"


def test_qr_url_is_base_url_c_token_and_verifies(logged, app, clock):
    """Covers D31: URL = BASE_URL/c/<token>, token verifies for the open session."""
    clock.set(T0)
    logged.post("/lecturer/sessions")
    url = decode_qr(state(logged)["qr"])
    assert re.fullmatch(r"https://test\.example/c/[A-Za-z0-9_-]+", url)
    creds = RotatingCredentials("test-secret-key", clock)
    assert creds.verify_qr(url.rsplit("/", 1)[1]) == open_id(app)


def test_code_matches_credentials_for_session(logged, app, clock):
    """Covers D30: displayed code is the current code of the open session."""
    clock.set(T0)
    logged.post("/lecturer/sessions")
    creds = RotatingCredentials("test-secret-key", clock)
    assert state(logged)["code"] == creds.current_code(open_id(app))


def test_qr_slot_edges(logged, clock):
    """Covers D31: QR identical at 9.999 s, new at 10.0 s."""
    logged.post("/lecturer/sessions")
    clock.set(T0)
    first = state(logged)["qr"]
    clock.set(T0 + 9.999)
    assert state(logged)["qr"] == first
    clock.set(T0 + 10.0)
    assert state(logged)["qr"] != first


def test_code_slot_edges(logged, clock):
    """Covers D31: code identical at 4.999 s, new at 5.0 s (deterministic with the test secret)."""
    logged.post("/lecturer/sessions")
    clock.set(T0)
    first = state(logged)["code"]
    clock.set(T0 + 4.999)
    assert state(logged)["code"] == first
    clock.set(T0 + 5.0)
    assert state(logged)["code"] != first


def test_reopen_gives_new_session_id_in_token(logged, app, clock):
    """Covers FR-1.13: after close and reopen the token carries the new session id."""
    clock.set(T0)
    logged.post("/lecturer/sessions")
    first_id = open_id(app)
    first_token = token_of(state(logged)["qr"])
    logged.post("/lecturer/sessions/close")
    assert state(logged)["open"] is False
    logged.post("/lecturer/sessions")
    second_id = open_id(app)
    assert second_id != first_id
    creds = RotatingCredentials("test-secret-key", clock)
    new_token = token_of(state(logged)["qr"])
    assert creds.verify_qr(new_token) == second_id
    assert new_token != first_token
    assert creds.verify_qr(first_token) == first_id  # old token still genuine, but for the old session


def test_api_401_json_without_pin_and_no_leak(client, logged, app):
    """Covers D4: anonymous client gets 401 JSON with no code or QR, even with a session open."""
    logged.post("/lecturer/sessions")
    code = state(logged)["code"]
    anon = app.test_client()
    resp = anon.get("/api/projector")
    assert resp.status_code == 401
    assert resp.is_json
    body = resp.get_data(as_text=True)
    assert "data:image" not in body and "qr" not in resp.get_json()
    assert code not in re.sub(r"\s", "", body) or code == ""
    assert "code" not in resp.get_json()


def test_wrong_pin_login_does_not_unlock_api(client):
    """Covers D4: a failed login leaves the API locked."""
    client.post("/lecturer/login", data={"pin": "0000"})
    assert client.get("/api/projector").status_code == 401


def test_page_structure_and_no_external_url(logged):
    """Covers FR-1.5, KISS: id=qr, id=code, no http(s) URL, no CDN, script is local."""
    html = logged.get("/lecturer/projector").get_data(as_text=True)
    assert 'id="qr"' in html and 'id="code"' in html
    assert not re.search(r"https?://", html)
    assert "cdn" not in html.lower() and "//" not in re.sub(r"<!--.*?-->", "", html, flags=re.S).replace("</", "")
    assert "projector.js" in html


def test_projector_js_polls_at_1000_ms_and_is_local():
    """Covers D31: polling period 1000 ms, no external URL."""
    js = (Path(__file__).parent.parent / "app" / "static" / "projector.js").read_text()
    assert re.search(r"POLL_MS\s*=\s*1000\b", js)
    assert "setInterval(poll, POLL_MS)" in js
    assert not re.search(r"https?://", js)
