"""Allow-list editor (T9, FR-1.4, UC-6)."""
import pytest

URL = "/lecturer/allow-list"
INVALID = b"This is not a valid network range (e.g. 192.0.2.0/24)."


@pytest.fixture
def logged(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def check_in_status(app, ip):
    services = app.extensions["services"]
    path = services["session_service"].projector_state().check_in_url.split("test.example")[1]
    return app.test_client().get(path, environ_base={"REMOTE_ADDR": ip}).status_code


@pytest.mark.parametrize("method", ["get", "post"])
def test_requires_pin(client, method):
    response = getattr(client, method)(URL)
    assert response.status_code == 302 and response.headers["Location"].endswith("/lecturer/login")


def test_dashboard_links_to_editor(logged):
    assert URL.encode() in logged.get("/lecturer").data


def test_empty_list_warns_and_shows_hint(logged):
    html = logged.get(URL).get_data(as_text=True)
    assert "Nobody can check in until you add the campus network." in html
    assert "campus Wi-Fi" in html


def test_valid_ipv4_and_ipv6_used_at_once(app, logged):
    app.extensions["services"]["session_service"].open_session()
    assert check_in_status(app, "192.0.2.10") == 403
    response = logged.post(URL, data={"ranges": "192.0.2.0/24\n2001:db8::/32\n"})
    assert response.status_code == 302
    assert check_in_status(app, "192.0.2.10") == 200
    assert check_in_status(app, "2001:db8::1") == 200
    assert check_in_status(app, "198.51.100.7") == 403
    html = logged.get(URL).get_data(as_text=True)
    assert "192.0.2.0/24" in html and "2001:db8::/32" in html
    assert "Nobody can check in" not in html


def test_invalid_line_keeps_previous_list_and_typed_text(logged):
    logged.post(URL, data={"ranges": "192.0.2.0/24"})
    response = logged.post(URL, data={"ranges": "198.51.100.0/24\nnot-an-ip"})
    assert response.status_code == 400 and INVALID in response.data
    assert b"not-an-ip" in response.data and b"198.51.100.0/24" in response.data
    saved = logged.get(URL).get_data(as_text=True)
    assert "192.0.2.0/24" in saved and "198.51.100.0/24" not in saved


def test_saving_empty_text_clears_list(logged):
    logged.post(URL, data={"ranges": "192.0.2.0/24"})
    logged.post(URL, data={"ranges": ""})
    assert b"Nobody can check in" in logged.get(URL).data
