"""Ids outside the SQLite 64-bit range behave exactly like unknown ids: a clean 404/400, never a 500."""
import pytest

HUGE = 10**30


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def test_attendance_api_huge_id(lecturer):
    resp = lecturer.get(f"/api/sessions/{HUGE}/attendance")
    assert resp.status_code == 404
    assert resp.get_json() == lecturer.get("/api/sessions/999/attendance").get_json()


def test_photo_page_and_upload_huge_id(lecturer):
    assert lecturer.get(f"/lecturer/sessions/{HUGE}/photo").status_code == 404
    assert lecturer.post(f"/lecturer/sessions/{HUGE}/photo", data={}).status_code == 400
    upload = {"photo": (__import__("io").BytesIO(b"x"), "p.jpg")}
    resp = lecturer.post(f"/lecturer/sessions/{HUGE}/photo", data=upload, content_type="multipart/form-data")
    assert resp.status_code == 404


def test_poll_routes_huge_id(lecturer):
    assert lecturer.get(f"/api/polls/{HUGE}/results").status_code == 404
    assert lecturer.post(f"/lecturer/polls/{HUGE}/close").status_code == 404
    assert lecturer.post("/poll/vote", data={"poll_id": HUGE, "option_id": 1}).status_code == 404
    assert lecturer.post("/poll/vote", data={"poll_id": 1, "option_id": HUGE}).status_code == 404
