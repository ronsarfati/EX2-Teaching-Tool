"""D37: signed device token mirrored on the phone; the older stored token beats a fresh cookie."""
import pytest

from app.web.device import COOKIE_NAME, sign, verify_signed

ALREADY = b"You are already checked in for this class."


@pytest.fixture
def session(app):
    return app.extensions["services"]["session_service"].open_session()


def scan_url(app):
    return app.extensions["services"]["session_service"].projector_state().check_in_url.split("test.example")[1]


def code_now(app):
    return app.extensions["services"]["session_service"].projector_state().code


def sync(client, stored=()):
    return client.post("/device/sync", json={"stored": list(stored)})


def cookie_of(client):
    return client.get_cookie(COOKIE_NAME).value


def checked_in_phone(app):
    """A phone that checked in; returns it with the token its JS would have mirrored."""
    phone = app.test_client()
    phone.get(scan_url(app))
    token = sync(phone).get_json()["token"]
    assert phone.post("/checkin", data={"nickname": "Fox", "code": code_now(app)}).status_code == 200
    return phone, token


def test_signed_round_trip(app):
    with app.app_context():
        signed = sign("abcdefghijklmnop")
        assert verify_signed(signed) == "abcdefghijklmnop"


@pytest.mark.parametrize("value", ["", "abcdefghijklmnop", "abcdefghijklmnop.AAAA", "a.b.c", "short.sig"])
def test_forged_or_malformed_tokens_rejected(app, value):
    with app.app_context():
        assert verify_signed(value) is None


def test_token_signed_with_another_key_rejected(app):
    with app.app_context():
        signed = sign("abcdefghijklmnop")
        app.config["SECRET_KEY"] = "other"
        assert verify_signed(signed) is None


def test_cookie_is_signed_and_keeps_flags(app, session):
    phone = app.test_client()
    header = phone.get(scan_url(app)).headers["Set-Cookie"]
    assert "HttpOnly" in header and "SameSite=Lax" in header and "Max-Age=31536000" in header
    with app.app_context():
        assert verify_signed(cookie_of(phone)) is not None


def test_sync_returns_token_and_no_change_without_stored(app, session):
    phone = app.test_client()
    phone.get(scan_url(app))
    data = sync(phone).get_json()
    assert data["changed"] is False and data["token"] == cookie_of(phone)


def test_cleared_cookie_then_scan_again_is_refused(app, session):
    phone, token = checked_in_phone(app)
    phone.delete_cookie(COOKIE_NAME)
    phone.get(scan_url(app))  # a fresh cookie is issued: the window opens under the new identity
    data = sync(phone, [token]).get_json()  # what device.js does on load
    assert data["changed"] is True and data["token"] == token
    assert cookie_of(phone) == token  # cookie re-set to the stored token
    again = phone.get(scan_url(app))
    assert again.status_code == 409 and ALREADY in again.data


def test_confirm_with_stored_field_is_refused_after_cookie_clear(app, session):
    phone, token = checked_in_phone(app)
    phone.delete_cookie(COOKIE_NAME)
    phone.get(scan_url(app))
    response = phone.post("/checkin", data={"nickname": "Fox2", "code": code_now(app), "dt_stored": token})
    assert response.status_code != 200 and b"You are checked in" not in response.data
    assert cookie_of(phone) == token


def test_forged_stored_token_is_ignored(app, session):
    phone = app.test_client()
    phone.get(scan_url(app))
    before = cookie_of(phone)
    data = sync(phone, ["abcdefghijklmnop.forgedsignature"]).get_json()
    assert data["changed"] is False and cookie_of(phone) == before


def test_new_phone_without_stored_token_checks_in_as_before(app, session):
    phone = app.test_client()
    phone.get(scan_url(app))
    assert phone.post("/checkin", data={"nickname": "Fox", "code": code_now(app)}).status_code == 200


def test_legacy_unsigned_cookie_still_accepted_and_upgraded(app, session):
    phone = app.test_client()
    phone.set_cookie(COOKIE_NAME, "legacytoken1234567890")
    phone.get(scan_url(app))
    assert phone.post("/checkin", data={"nickname": "Fox", "code": code_now(app)}).status_code == 200
    with app.app_context():
        assert verify_signed(cookie_of(phone)) == "legacytoken1234567890"


def test_forged_cookie_is_replaced(app, session):
    phone = app.test_client()
    phone.set_cookie(COOKIE_NAME, "abcdefghijklmnop.forgedsignature")
    phone.get(scan_url(app))
    with app.app_context():
        assert verify_signed(cookie_of(phone)) is not None


def test_poll_vote_after_cookie_clear_is_refused(app):
    polls = app.extensions["services"]["poll_service"]
    poll = polls.create("Q?", ["a", "b"])
    phone = app.test_client()
    phone.get("/poll")
    token = sync(phone).get_json()["token"]
    form = {"poll_id": poll.id, "option_id": poll.options[0].id}
    assert phone.post("/poll/vote", data=form).status_code == 302
    phone.delete_cookie(COOKIE_NAME)
    phone.get("/poll")
    sync(phone, [token])  # device.js restores the old identity
    again = phone.post("/poll/vote", data=form)
    assert again.status_code != 302 and b"You have already voted." in again.data


def test_poll_vote_with_stored_field_is_refused(app):
    polls = app.extensions["services"]["poll_service"]
    poll = polls.create("Q?", ["a", "b"])
    phone = app.test_client()
    phone.get("/poll")
    token = sync(phone).get_json()["token"]
    form = {"poll_id": poll.id, "option_id": poll.options[0].id}
    phone.post("/poll/vote", data=form)
    phone.delete_cookie(COOKIE_NAME)
    again = phone.post("/poll/vote", data={**form, "dt_stored": token})
    assert b"You have already voted." in again.data


def test_pages_load_the_mirror_script(app, session):
    html = app.test_client().get(scan_url(app)).get_data(as_text=True)
    assert "device.js" in html and 'name="dt_stored"' in html
    assert app.test_client().get("/static/device.js").status_code == 200
