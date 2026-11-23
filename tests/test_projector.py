"""Projector JSON and page (FR-1.5, FR-1.8, FR-1.13, FR-6.3)."""
import base64
import re

import cv2
import numpy as np
import pytest


@pytest.fixture
def logged(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def decode_qr(data_uri: str) -> str:
    png = base64.b64decode(data_uri.removeprefix("data:image/png;base64,"))
    image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    return cv2.QRCodeDetector().detectAndDecode(image)[0]


def test_api_requires_pin(client):
    assert client.get("/api/projector").status_code == 401


def test_page_requires_pin(client):
    assert client.get("/lecturer/projector").status_code == 302


def test_page_has_no_camera_or_cdn(logged):
    html = logged.get("/lecturer/projector").get_data(as_text=True)
    assert 'id="qr"' in html and 'id="code"' in html
    assert "getUserMedia" not in html and "http" not in html


def test_open_session_gives_decodable_qr_and_code(logged):
    logged.post("/lecturer/sessions")
    data = logged.get("/api/projector").get_json()
    assert data["open"] is True
    assert decode_qr(data["qr"]).startswith("https://test.example/c/")
    assert re.fullmatch(r"\d{3}", data["code"])


def test_qr_changes_after_10s_and_code_after_5s(logged, clock):
    logged.post("/lecturer/sessions")
    clock.set(1_000_000.0)  # start of a 10 s slot
    first = logged.get("/api/projector").get_json()
    clock.advance(5)
    mid = logged.get("/api/projector").get_json()
    assert mid["qr"] == first["qr"]  # same 10 s slot
    clock.advance(5)
    later = logged.get("/api/projector").get_json()
    assert later["qr"] != first["qr"]
    assert decode_qr(later["qr"]) != decode_qr(first["qr"])


def test_code_changes_across_5s_slices(logged, clock, app):
    logged.post("/lecturer/sessions")
    codes = set()
    for _ in range(40):  # 3 digits: one pair may collide by chance, 40 slices cannot all be equal
        codes.add(logged.get("/api/projector").get_json()["code"])
        clock.advance(5)
    assert len(codes) > 1


def test_closed_session_shows_nothing(logged):
    assert logged.get("/api/projector").get_json() == {"open": False, "qr": None, "code": None}
    logged.post("/lecturer/sessions")
    logged.post("/lecturer/sessions/close")
    assert logged.get("/api/projector").get_json()["qr"] is None
