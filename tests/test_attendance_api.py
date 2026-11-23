"""Live attendance JSON (T10): rows, N, privacy, auth, unknown id."""
import pytest


@pytest.fixture
def session(app):
    s = app.extensions["services"]
    return s["session_service"].open_session()


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def check_in(app, nickname, code=None):
    phone = app.test_client()
    s = app.extensions["services"]["session_service"].projector_state()
    phone.get(s.check_in_url.split("test.example")[1])
    return phone.post("/checkin", data={"nickname": nickname, "code": code or s.code})


def test_check_in_listed_with_n_plus_one(app, session, lecturer):
    url = f"/api/sessions/{session.id}/attendance"
    assert lecturer.get(url).get_json()["n"] == 0
    check_in(app, "Fox")
    data = lecturer.get(url).get_json()
    assert data["n"] == 1 and [c["nickname"] for c in data["check_ins"]] == ["Fox"]
    assert data["head_count"] is None and data["consistency"] is None


def test_wrong_code_does_not_change_n(app, session, lecturer):
    check_in(app, "Fox", code="abcd")
    assert lecturer.get(f"/api/sessions/{session.id}/attendance").get_json()["n"] == 0


def test_json_has_no_token_or_ip(app, session, lecturer):
    check_in(app, "Fox")
    body = lecturer.get(f"/api/sessions/{session.id}/attendance").get_data(as_text=True)
    assert "token" not in body and "ip" not in body.replace("nickname", "")


def test_requires_pin(client, session):
    response = client.get(f"/api/sessions/{session.id}/attendance")
    assert response.status_code == 401 and "error" in response.get_json()


def test_unknown_session_is_clean_404(lecturer):
    response = lecturer.get("/api/sessions/999/attendance")
    assert response.status_code == 404 and response.get_json() == {"error": "There is no attendance check-in right now."}


def test_dashboard_embeds_poll_script(app, session, lecturer):
    html = lecturer.get("/lecturer").get_data(as_text=True)
    assert "poll_json.js" in html and "/lecturer/allow-list" not in html
