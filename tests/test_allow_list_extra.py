"""Allow-list editor, extra cases (T9, FR-1.4, UC-6, SD-6, D31, NFR-7, NFR-8)."""
import pytest

URL = "/lecturer/allow-list"
INVALID = "This is not a valid network range (e.g. 192.0.2.0/24)."
OFF_CAMPUS = "Check-in only works on the university Wi-Fi. Please connect to it and scan again."
WARNING = "Nobody can check in until you add the campus network."


@pytest.fixture
def logged(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def checkin_path(app):
    state = app.extensions["services"]["session_service"].projector_state()
    return state.check_in_url.split("test.example")[1]


def visit(app, ip):
    return app.test_client().get(checkin_path(app), environ_base={"REMOTE_ADDR": ip})


def stored(client):
    html = client.get(URL).get_data(as_text=True)
    return html.split("<textarea", 1)[1].split(">", 1)[1].split("</textarea>")[0]


def test_get_without_pin_redirects_to_login(client):
    """Covers FR-1.4, NFR-8."""
    r = client.get(URL)
    assert r.status_code == 302 and r.headers["Location"].endswith("/lecturer/login")
    assert b"textarea" not in r.data


def test_post_without_pin_does_not_change_list(client):
    """Covers FR-1.4, NFR-8."""
    client.post("/lecturer/login", data={"pin": "1234"})
    client.post(URL, data={"ranges": "192.0.2.0/24"})
    anon = client.application.test_client()
    r = anon.post(URL, data={"ranges": "198.51.100.0/24"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/lecturer/login")
    assert stored(client).strip() == "192.0.2.0/24"


def test_mixed_valid_and_invalid_is_atomic_and_escaped(logged):
    """Covers FR-1.4, D31, SRS error table."""
    logged.post(URL, data={"ranges": "192.0.2.0/24"})
    r = logged.post(URL, data={"ranges": "198.51.100.0/24\n<script>x</script>"})
    html = r.get_data(as_text=True)
    assert r.status_code == 400
    assert INVALID in html
    assert "198.51.100.0/24" in html  # typed text kept
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<script>x</script>" not in html
    assert stored(logged).strip() == "192.0.2.0/24"
    assert "198.51.100.0/24" not in logged.get(URL).get_data(as_text=True)


def test_blank_lines_and_spaces_ignored(logged):
    """Covers FR-1.4."""
    r = logged.post(URL, data={"ranges": "\n   \n  192.0.2.0/24  \n\n\t198.51.100.0/24\t\n  \n"})
    assert r.status_code == 302
    assert stored(logged).split() == ["192.0.2.0/24", "198.51.100.0/24"]


def test_ipv6_cidr_saved(logged):
    """Covers FR-1.4 (IPv6)."""
    logged.post(URL, data={"ranges": "2001:db8:1::/48"})
    assert stored(logged).strip() == "2001:db8:1::/48"


def test_host_bits_cidr_normalised(logged):
    """Covers FR-1.4 (normalisation)."""
    logged.post(URL, data={"ranges": "192.0.2.77/24\n2001:db8::5/32"})
    assert stored(logged).split() == ["192.0.2.0/24", "2001:db8::/32"]


def test_saving_empty_text_refuses_everyone_off_campus(app, logged):
    """Covers FR-1.4, D31 (empty list refuses all)."""
    app.extensions["services"]["session_service"].open_session()
    logged.post(URL, data={"ranges": "192.0.2.0/24"})
    assert visit(app, "192.0.2.10").status_code == 200
    r = logged.post(URL, data={"ranges": ""})
    assert r.status_code == 302
    assert stored(logged).strip() == ""
    refused = visit(app, "192.0.2.10")
    assert refused.status_code == 403
    assert OFF_CAMPUS in refused.get_data(as_text=True)


def test_whitespace_only_text_also_empties_list(logged):
    """Covers FR-1.4, D31."""
    logged.post(URL, data={"ranges": "192.0.2.0/24"})
    logged.post(URL, data={"ranges": "  \n \n"})
    assert WARNING in logged.get(URL).get_data(as_text=True)


def test_saved_list_shown_in_textarea(logged):
    """Covers FR-1.4, UC-6."""
    logged.post(URL, data={"ranges": "198.51.100.0/24\n192.0.2.0/24"})
    assert sorted(stored(logged).split()) == ["192.0.2.0/24", "198.51.100.0/24"]


def test_edit_applies_immediately_to_new_ip(app, logged):
    """Covers FR-1.4, SD-6 (no restart)."""
    app.extensions["services"]["session_service"].open_session()
    assert visit(app, "203.0.113.9").status_code == 403
    logged.post(URL, data={"ranges": "203.0.113.0/24"})
    assert visit(app, "203.0.113.9").status_code == 200
    logged.post(URL, data={"ranges": "192.0.2.0/24"})
    assert visit(app, "203.0.113.9").status_code == 200  # D32: now off campus, still accepted


def test_warning_only_when_empty(logged):
    """Covers FR-1.4, D31."""
    assert WARNING in logged.get(URL).get_data(as_text=True)
    logged.post(URL, data={"ranges": "192.0.2.0/24"})
    assert WARNING not in logged.get(URL).get_data(as_text=True)
    logged.post(URL, data={"ranges": ""})
    assert WARNING in logged.get(URL).get_data(as_text=True)


def test_lecturer_ip_never_stored(app, config, logged):
    """Covers NFR-7 (client IP never stored)."""
    ip = "203.0.113.77"
    c = app.test_client()
    env = {"REMOTE_ADDR": ip}
    c.post("/lecturer/login", data={"pin": "1234"}, environ_base=env)
    c.get(URL, environ_base=env)
    c.post(URL, data={"ranges": "192.0.2.0/24"}, environ_base=env)
    assert stored(c) .strip() == "192.0.2.0/24"
    with open(config.database_path, "rb") as f:
        assert ip.encode() not in f.read()
