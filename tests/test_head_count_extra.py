"""T11 extra tests: independent D7 oracle, labels, auth, size limit, privacy, error paths, live table.

Covers FR-1.15, FR-1.16, FR-1.17, D7, D21, D31, NFR-8.
"""
import io
import math
import os
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app import create_app
from app.errors import DetectorUnavailableError, UnreadablePhotoError
from app.services.consistency import ConsistencyResult
from tests.fakes import FakeHeadCounter

UNREADABLE = "We could not read this photo. Please try another one."
UNAVAILABLE = "Head count is not available right now."
ROOT = Path(__file__).resolve().parent.parent


def oracle(n: int, d: int) -> bool:
    """D7 written from the decision text with exact integer maths, sharing nothing with the app."""
    miss = max(7, math.ceil(15 * n / 100 if (15 * n) % 100 else (15 * n) // 100))
    extra = max(4, math.ceil(10 * n / 100 if (10 * n) % 100 else (10 * n) // 100))
    return n - miss <= d <= n + extra


def make_client(config, clock, counter):
    app = create_app(config, clock=clock, head_counter=counter)
    client = app.test_client()
    client.post("/lecturer/login", data={"pin": "1234"})
    client.post("/lecturer/sessions")
    return client, app


def upload(client, data=b"img", session_id=1, content_type="image/jpeg", name="p.jpg"):
    return client.post(
        f"/lecturer/sessions/{session_id}/photo",
        data={"photo": (io.BytesIO(data), name, content_type)},
        content_type="multipart/form-data",
    )


def test_d7_matches_independent_oracle_full_grid():
    """Covers D7: N 0..300 x D 0..400 against a separate implementation."""
    bad = [(n, d) for n in range(301) for d in range(401)
           if ConsistencyResult.evaluate(n, d).consistent != oracle(n, d)]
    assert bad == []


def test_labels_exact_strings():
    """Covers FR-1.16: only the two exact labels exist."""
    assert ConsistencyResult.evaluate(40, 40).label() == "consistent"
    assert ConsistencyResult.evaluate(40, 0).label() == "anomaly"
    labels = {ConsistencyResult.evaluate(n, d).label() for n in range(0, 60) for d in range(0, 90)}
    assert labels == {"consistent", "anomaly"}


def test_upload_without_pin_refused_and_d_unchanged(config, clock):
    """Covers FR-1.15 (PIN) : an anonymous upload is redirected and never reaches the counter."""
    counter = FakeHeadCounter(count=5)
    client, app = make_client(config, clock, counter)
    anon = app.test_client()
    response = upload(anon)
    assert response.status_code == 302 and "/lecturer/login" in response.headers["Location"]
    assert counter.received == []
    assert app.extensions["services"]["sessions"].get(1).head_count is None


def test_oversized_upload_clean_message(config, clock):
    """Covers NFR-8: > MAX_CONTENT_LENGTH gives a clean error, no traceback, app still serves."""
    counter = FakeHeadCounter(count=5)
    client, app = make_client(config, clock, counter)
    limit = app.config["MAX_CONTENT_LENGTH"]
    response = upload(client, b"\0" * (limit + 1024))
    text = response.get_data(as_text=True)
    assert response.status_code == 413
    assert "Traceback" not in text and "Werkzeug" not in text and "RequestEntityTooLarge" not in text
    assert counter.received == []
    assert client.get("/lecturer").status_code == 200


@pytest.mark.parametrize("ctype,name,data", [
    ("text/plain", "a.txt", b"hello world"),
    ("application/pdf", "a.pdf", b"%PDF-1.4 fake"),
    ("image/jpeg", "a.jpg", b"\xff\xd8\xff"),  # truncated JPEG header
    ("image/png", "a.png", b"\x89PNG\r\n\x1a\n"),
])
def test_non_image_or_truncated_is_unreadable(config, clock, tmp_path, ctype, name, data):
    """Covers FR-1.15 error table: real adapter, bad bytes -> unreadable message (400)."""
    from app.adapters.head_counter import YuNetHeadCounter
    client, app = make_client(config, clock, YuNetHeadCounter(str(tmp_path / "absent.onnx")))
    response = upload(client, data, content_type=ctype, name=name)
    text = response.get_data(as_text=True)
    assert response.status_code == 400 and UNREADABLE in text and "Traceback" not in text
    assert app.extensions["services"]["sessions"].get(1).head_count is None


def test_photo_bytes_never_persisted(config, clock, tmp_path):
    """Covers FR-1.17: no new file under the project or tmp dirs, and no BLOB/photo column in the DB."""
    counter = FakeHeadCounter(count=3)
    client, app = make_client(config, clock, counter)
    tmp = Path(tempfile.gettempdir())

    def snap():
        out = set()
        for base in (ROOT, tmp):
            for dirpath, dirs, files in os.walk(base):
                dirs[:] = [x for x in dirs if x not in {".git", ".venv", "__pycache__", ".pytest_cache"}]
                out.update(os.path.join(dirpath, f) for f in files)
        return out

    skip = (".db", "-wal", "-shm", "-journal", ".coverage", ".pyc")
    before = snap()
    payload = b"\xff\xd8\xff" + os.urandom(4000)
    upload(client, payload)
    new = {p for p in snap() - before if not p.endswith(skip) and ".coverage" not in p}
    assert new == set()

    con = sqlite3.connect(config.database_path)
    for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for _, col, ctype, *_ in con.execute(f"PRAGMA table_info({table})").fetchall():
            assert "BLOB" not in (ctype or "").upper(), (table, col)
            assert not re.search(r"photo|image|picture", col, re.I), (table, col)
        for row in con.execute(f"SELECT * FROM {table}").fetchall():
            assert not any(isinstance(v, bytes) for v in row)
    dump = b"".join(con.iterdump().__iter__().__next__().encode() for _ in range(1))
    assert payload not in dump
    con.close()
    assert payload[:50] not in Path(config.database_path).read_bytes()


def test_model_missing_message_status_and_app_still_serves(config, clock):
    """Covers SRS error table / design: 503 'not available', other pages keep working."""
    client, _ = make_client(config, clock, FakeHeadCounter(error=DetectorUnavailableError()))
    response = upload(client)
    text = response.get_data(as_text=True)
    assert response.status_code == 503 and UNAVAILABLE in text and "Traceback" not in text
    assert client.get("/lecturer").status_code == 200
    assert client.get("/lecturer/sessions/1/photo").status_code == 200
    assert client.get("/api/sessions/1/attendance").get_json()["head_count"] is None


def test_real_adapter_without_model_via_route(config, clock, tmp_path):
    """Covers SRS error table: real adapter, valid PNG, model file absent -> 503."""
    import cv2
    import numpy as np
    from app.adapters.head_counter import YuNetHeadCounter
    client, _ = make_client(config, clock, YuNetHeadCounter(str(tmp_path / "absent.onnx")))
    ok, png = cv2.imencode(".png", np.zeros((40, 40, 3), np.uint8))
    response = upload(client, png.tobytes(), content_type="image/png", name="a.png")
    assert response.status_code == 503 and UNAVAILABLE in response.get_data(as_text=True)
    assert client.get("/").status_code in (200, 302, 404)


def test_live_api_returns_head_count_and_consistency(config, clock):
    """Covers FR-1.14/1.16: API fields after upload (N=0, D=4 -> consistent; D=5 -> anomaly)."""
    counter = FakeHeadCounter(count=4)
    client, _ = make_client(config, clock, counter)
    upload(client)
    data = client.get("/api/sessions/1/attendance").get_json()
    assert (data["head_count"], data["consistency"]) == (4, "consistent")
    counter.count = 5
    upload(client)
    data = client.get("/api/sessions/1/attendance").get_json()
    assert (data["head_count"], data["consistency"]) == (5, "anomaly")


def test_table_js_uses_textcontent_for_d_and_status():
    """Covers FR-1.14: the table script shows D and status through textContent, never innerHTML."""
    js = (ROOT / "app/static/poll_json.js").read_text()
    assert "dEl.textContent" in js and "statusEl.textContent" in js and "nEl.textContent" in js
    code = "\n".join(line.split("//")[0] for line in js.splitlines())  # ignore comments
    assert "innerHTML" not in code and "insertAdjacentHTML" not in code
    html = (ROOT / "app/templates/lecturer.html").read_text()
    for ident in ('id="d"', 'id="status"', 'id="n"'):
        assert ident in html


def test_record_on_closed_session_ok(config, clock):
    """Covers D31: a photo can be counted after the session is closed."""
    counter = FakeHeadCounter(count=2)
    client, app = make_client(config, clock, counter)
    client.post("/lecturer/sessions/close")
    assert not app.extensions["services"]["sessions"].get(1).is_open()
    response = upload(client)
    assert response.status_code == 200
    data = client.get("/api/sessions/1/attendance").get_json()
    assert data["open"] is False and data["head_count"] == 2 and data["consistency"] == "consistent"


def test_two_successive_photos_second_wins(config, clock):
    """Covers D31: the second D replaces the first, also in the stored row."""
    counter = FakeHeadCounter(count=30)
    client, app = make_client(config, clock, counter)
    upload(client)
    counter.count = 1
    upload(client)
    assert app.extensions["services"]["sessions"].get(1).head_count == 1
    assert len(counter.received) == 2
