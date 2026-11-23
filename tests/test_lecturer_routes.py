"""Lecturer PIN gate and open / close routes (FR-1.1, FR-1.13, FR-6.1)."""
import pytest


@pytest.fixture
def logged(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


@pytest.mark.parametrize("method,path", [("get", "/lecturer"), ("post", "/lecturer/sessions"),
                                         ("post", "/lecturer/sessions/close")])
def test_pages_redirect_without_pin(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 302 and response.headers["Location"].endswith("/lecturer/login")


def test_login_page_renders(client):
    assert b'name="pin"' in client.get("/lecturer/login").data


def test_wrong_pin(client):
    response = client.post("/lecturer/login", data={"pin": "0000"})
    assert response.status_code == 401 and b"Wrong PIN." in response.data
    assert client.get("/lecturer").status_code == 302


def test_missing_pin_field_is_wrong(client):
    assert client.post("/lecturer/login").status_code == 401


def test_right_pin_unlocks(logged):
    response = logged.get("/lecturer")
    assert response.status_code == 200 and b"Open session" in response.data


def test_open_then_second_open_refused(logged):
    response = logged.post("/lecturer/sessions")
    assert response.status_code == 302 and response.headers["Location"].endswith("/lecturer/projector")
    assert b"Close session" in logged.get("/lecturer").data
    response = logged.post("/lecturer/sessions")
    assert response.status_code == 409 and b"A session is already open. Close it first." in response.data


def test_close_then_open_again(logged):
    logged.post("/lecturer/sessions")
    assert logged.post("/lecturer/sessions/close").status_code == 302
    assert b"Open session" in logged.get("/lecturer").data
    assert logged.post("/lecturer/sessions").status_code == 302
