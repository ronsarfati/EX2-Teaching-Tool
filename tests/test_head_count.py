"""Photo head count: route with a fake counter, privacy, replacement, and the real YuNet adapter (FR-1.15-FR-1.17)."""
import io
import os
import tempfile
import threading
from pathlib import Path

import cv2
import numpy as np
import pytest

from app import create_app
from app.adapters.head_counter import YuNetHeadCounter
from app.errors import DetectorUnavailableError, UnreadablePhotoError
from tests.fakes import FakeHeadCounter

UNREADABLE = "We could not read this photo. Please try another one."


@pytest.fixture
def counter() -> FakeHeadCounter:
    return FakeHeadCounter(count=40)


@pytest.fixture
def lecturer(config, clock, counter):
    app = create_app(config, clock=clock, head_counter=counter)
    client = app.test_client()
    client.post("/lecturer/login", data={"pin": "1234"})
    client.post("/lecturer/sessions")
    return client, app


def upload(client, data: bytes = b"fake-image-bytes", session_id: int = 1):
    return client.post(
        f"/lecturer/sessions/{session_id}/photo",
        data={"photo": (io.BytesIO(data), "p.jpg")},
        content_type="multipart/form-data",
    )


def test_photo_page_requires_pin(client):
    response = client.get("/lecturer/sessions/1/photo")
    assert response.status_code == 302 and "/lecturer/login" in response.headers["Location"]


def test_upload_shows_n_d_status(lecturer, counter):
    client, _ = lecturer
    response = upload(client)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "<strong>0</strong> / detected <strong>40</strong>" in html and "anomaly" in html
    assert counter.received == [b"fake-image-bytes"]


def test_live_api_shows_d_and_status(lecturer):
    client, _ = lecturer
    upload(client)
    data = client.get("/api/sessions/1/attendance").get_json()
    assert (data["head_count"], data["consistency"]) == (40, "anomaly")


def test_new_photo_replaces_d(lecturer, counter):
    client, _ = lecturer
    upload(client)
    counter.count = 3  # N = 0, upper = 4: consistent
    upload(client)
    data = client.get("/api/sessions/1/attendance").get_json()
    assert (data["head_count"], data["consistency"]) == (3, "consistent")


def test_no_d_means_no_status(lecturer):
    client, _ = lecturer
    data = client.get("/api/sessions/1/attendance").get_json()
    assert (data["head_count"], data["consistency"]) == (None, None)


def test_unreadable_photo_message(config, clock):
    app = create_app(config, clock=clock, head_counter=FakeHeadCounter(error=UnreadablePhotoError()))
    client = app.test_client()
    client.post("/lecturer/login", data={"pin": "1234"})
    client.post("/lecturer/sessions")
    response = upload(client)
    assert response.status_code == 400 and UNREADABLE in response.get_data(as_text=True)


def test_missing_file_field_is_unreadable(lecturer):
    client, _ = lecturer
    response = client.post("/lecturer/sessions/1/photo", data={})
    assert response.status_code == 400 and UNREADABLE in response.get_data(as_text=True)


def test_unknown_session_is_404(lecturer):
    client, _ = lecturer
    assert upload(client, session_id=99).status_code == 404


def test_photo_not_written_to_disk(lecturer, tmp_path):
    client, _ = lecturer

    def snapshot():
        return {str(p) for root in (tmp_path, Path(tempfile.gettempdir())) for p in root.rglob("*")}

    before = snapshot()
    upload(client, b"\xff\xd8\xff" + os.urandom(2000))
    new = {p for p in snapshot() - before if not p.endswith(("-wal", "-shm", ".db-journal"))}
    assert new == set()


def test_service_has_no_manual_set_method(lecturer):
    _, app = lecturer
    public = [n for n in dir(app.extensions["services"]["session_service"]) if not n.startswith("_")]
    assert not [n for n in public if "set" in n]


# ---- real adapter ----

def test_missing_model_is_unavailable(tmp_path):
    counter = YuNetHeadCounter(str(tmp_path / "absent.onnx"))
    ok, png = cv2.imencode(".png", np.zeros((50, 50, 3), np.uint8))
    with pytest.raises(DetectorUnavailableError) as info:
        counter.count_faces(png.tobytes())
    assert info.value.user_message == "Head count is not available right now."


@pytest.mark.parametrize("data", [b"not an image", b""])
def test_adapter_unreadable_bytes(tmp_path, data):
    with pytest.raises(UnreadablePhotoError):
        YuNetHeadCounter(str(tmp_path / "absent.onnx")).count_faces(data)


def test_default_threshold_is_0_4(config):
    assert config.face_score_threshold == 0.4


MODEL = os.environ.get("YUNET_MODEL_PATH", "models/face_detection_yunet_2023mar.onnx")
needs_model = pytest.mark.skipif(not os.path.isfile(MODEL), reason="YuNet model file not present")


@needs_model
def test_blank_large_image_has_no_face():
    ok, png = cv2.imencode(".png", np.full((3000, 4000, 3), 128, np.uint8))
    assert YuNetHeadCounter(MODEL).count_faces(png.tobytes()) == 0


@needs_model
def test_concurrent_calls_agree():
    ok, png = cv2.imencode(".png", np.full((600, 800, 3), 200, np.uint8))
    counter, results = YuNetHeadCounter(MODEL), []
    threads = [threading.Thread(target=lambda: results.append(counter.count_faces(png.tobytes()))) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results == [0] * 4
