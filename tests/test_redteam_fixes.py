"""Regression tests for the red-team findings F-03, F-04, F-07, F-08 and F-11 (correction/red_team.md)."""
import io
import logging

import cv2
import numpy as np
import pytest
from openpyxl import load_workbook

from app.adapters.head_counter import MAX_PIXELS, YuNetHeadCounter
from app.errors import UnreadablePhotoError
from app.services.export import _safe
from app.services.homework import _redact
from app.services.text import strip_invisible
from tests.test_export import CAMPUS, check_in, lecturer, run_session, services  # noqa: F401  (fixtures)

EMPTY_NICKNAME = "Please choose a nickname (not your real name or ID)."


def peers(url="https://github.com/alice/hw1"):
    return [("Submission B", url, None)]


# ---- F-03: control / format characters in nicknames ----

@pytest.mark.parametrize("raw, expected", [
    ("a\x01b", "ab"), ("\x01", ""), ("​", ""), ("‎‏", ""), ("⁠", ""), ("﻿", ""),
    ("\x85", ""), ("Fox​", "Fox"), ("Owl", "Owl"), ("שלום", "שלום"),
])
def test_strip_invisible(raw, expected):
    assert strip_invisible(raw) == expected


@pytest.mark.parametrize("nickname", ["\x01", "​", "‎‏", "⁠", "﻿", "\x00\x1f\x85"])
def test_invisible_only_nickname_refused(app, services, nickname):
    services["session_service"].open_session()
    phone = app.test_client()
    state = services["session_service"].projector_state()
    kw = {"environ_base": {"REMOTE_ADDR": CAMPUS}}
    phone.get(state.check_in_url.split("test.example")[1], **kw)
    response = phone.post("/checkin", data={"nickname": nickname, "code": state.code}, **kw)
    assert EMPTY_NICKNAME in response.get_data(as_text=True)


def test_control_char_nickname_stripped_and_xlsx_works(app, services, lecturer):  # noqa: F811
    run_session(app, services, ["a\x01b​"])
    stored = lecturer.get("/lecturer/export/checkins.csv").get_data().decode("utf-8-sig")
    assert "ab" in stored and "\x01" not in stored
    response = lecturer.get("/lecturer/export.xlsx")
    assert response.status_code == 200


def test_xlsx_survives_legacy_row_with_control_char(app, services, lecturer):  # noqa: F811
    """A row stored before the fix (control character in the database) must not make the export 500."""
    session = services["session_service"].open_session()
    services["db"].conn().execute(
        "INSERT INTO device(device_token, nickname, created_at) VALUES (?, ?, ?)", ("legacy-token", "a\x01b", 0.0))
    services["check_ins"].add(session.id, "legacy-token", "a\x01b", 1.0)
    response = lecturer.get("/lecturer/export.xlsx")
    assert response.status_code == 200
    sheet = load_workbook(io.BytesIO(response.get_data()))["Check-ins"]
    assert sheet["B2"].value == "ab"


def test_safe_still_neutralises_formulas_after_stripping():
    assert _safe("\x01=1+1") == "'=1+1"
    assert _safe("l1\nl2") == "l1\nl2"
    assert _safe("a\x00b") == "ab"


# ---- F-08: decompression bomb ----

def png_header_only(width, height):
    """A valid PNG whose pixel data is tiny: header says huge, decoding it would allocate gigabytes."""
    return cv2.imencode(".png", np.zeros((1, 1), np.uint8))[1].tobytes(), width, height


def forged_png(width, height):
    import struct
    import zlib
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    idat = zlib.compress(b"\x00" * 10)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def test_huge_png_refused_before_decoding(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("must not decode")
    monkeypatch.setattr(cv2, "imdecode", boom)
    with pytest.raises(UnreadablePhotoError):
        YuNetHeadCounter("missing.onnx")._decode(forged_png(16000, 16000))


def test_limit_is_40_megapixels():
    assert MAX_PIXELS == 40_000_000
    with pytest.raises(UnreadablePhotoError):
        YuNetHeadCounter._check_dimensions(forged_png(6001, 6667))
    YuNetHeadCounter._check_dimensions(forged_png(6000, 6666))  # just under: accepted


def test_normal_photo_still_decodes():
    ok, buffer = cv2.imencode(".jpg", np.full((60, 80, 3), 128, np.uint8))
    assert YuNetHeadCounter._decode(buffer.tobytes()).shape[:2] == (60, 80)


def test_garbage_is_unreadable():
    with pytest.raises(UnreadablePhotoError):
        YuNetHeadCounter._decode(b"not an image")


def test_upload_byte_cap(app, client):
    client.post("/lecturer/login", data={"pin": "1234"})
    client.post("/lecturer/sessions")
    big = io.BytesIO(b"0" * (25 * 1024 * 1024 + 1))
    response = client.post("/lecturer/sessions/1/photo", data={"photo": (big, "p.jpg")},
                           content_type="multipart/form-data")
    assert response.status_code == 413


# ---- F-11: no access log ----

def test_werkzeug_access_log_silenced(app):
    assert logging.getLogger("werkzeug").getEffectiveLevel() >= logging.ERROR


# ---- F-04: cookies and headers ----

def test_security_headers_on_every_response(client):
    for path in ("/ping", "/lecturer/login", "/does-not-exist"):
        response = client.get(path)
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_session_cookie_samesite_lax(app, client):
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    cookie = client.post("/lecturer/login", data={"pin": "1234"}).headers.get_all("Set-Cookie")
    assert any("SameSite=Lax" in c for c in cookie)


def test_device_cookie_samesite_lax(app, services):  # noqa: F811
    services["session_service"].open_session()
    state = services["session_service"].projector_state()
    phone = app.test_client()
    response = phone.get(state.check_in_url.split("test.example")[1], environ_base={"REMOTE_ADDR": CAMPUS})
    cookie = [c for c in response.headers.get_all("Set-Cookie") if c.startswith("dt=")]
    assert cookie and "SameSite=Lax" in cookie[0]


# ---- F-07: peer masking glued by - _ . ----

@pytest.mark.parametrize("text", [
    "alice-hw1 is good", "alice_hw1", "alice.dev", "ALICE-final", "hw1-final", "see Alice.", "x/alice/y",
])
def test_peer_names_masked_when_glued(text):
    out = _redact(text, peers())
    assert "alice" not in out.lower() and "hw1" not in out.lower()
    assert "Submission B" in out


@pytest.mark.parametrize("text", ["malice in wonderland", "Alicea", "chw1", "hw10"])
def test_unrelated_word_not_overmasked(text):
    assert _redact(text, peers()) == text


def test_url_still_masked():
    assert _redact("https://github.com/Alice/HW1 rocks", peers()) == "Submission B rocks"
