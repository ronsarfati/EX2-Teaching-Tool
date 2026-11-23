"""Remaining D30 rules unchanged after T20/T21 (QR 15 s, window 60 s, nickname 1-30, one check-in per device)."""
from tests.fakes import FakeClock  # noqa: F401


def _open(app):
    return app.extensions["services"]["session_service"].open_session()


def _state(app):
    return app.extensions["services"]["session_service"].projector_state()


def _path(state):
    return state.check_in_url.split("test.example")[1]


def test_qr_15s_accepted_and_15_001_refused(app, clock):
    _open(app)
    path = _path(_state(app))
    created = int(clock.now()) // 10 * 10
    clock.set(created + 15.0)
    assert app.test_client().get(path).status_code == 200
    clock.set(created + 15.001)
    r = app.test_client().get(path)
    assert r.status_code == 400 and b"This QR code has expired" in r.data


def test_window_60s_accepted_60_001_refused(app, clock):
    _open(app)
    c = app.test_client()
    c.get(_path(_state(app)))
    t0 = clock.now()
    clock.set(t0 + 60.0)
    assert c.post("/checkin", data={"nickname": "Fox", "code": _state(app).code}).status_code == 200
    _open_again = None
    c2 = app.test_client()
    app.extensions["services"]["session_service"].close_session()
    _open(app)
    c2.get(_path(_state(app)))
    t1 = clock.now()
    clock.set(t1 + 60.001)
    r = c2.post("/checkin", data={"nickname": "Cat", "code": _state(app).code})
    assert r.status_code == 400 and b"Your check-in time ran out" in r.data


def test_nickname_bounds_and_not_counted(app):
    _open(app)
    c = app.test_client()
    state = _state(app)
    c.get(_path(state))
    for bad in ("", "   ", "x" * 31):
        r = c.post("/checkin", data={"nickname": bad, "code": "0000"})
        assert r.status_code == 400 and b"Please choose a nickname" in r.data
    # none of those counted: 5 wrong codes still allowed, 6th refused
    wrong = f"{(int(state.code) + 1) % 10000:04d}"
    for _ in range(5):
        assert c.post("/checkin", data={"nickname": "ok", "code": wrong}).status_code == 400
    assert c.post("/checkin", data={"nickname": "ok", "code": state.code}).status_code == 429


def test_nickname_30_accepted(app):
    _open(app)
    c = app.test_client()
    state = _state(app)
    c.get(_path(state))
    assert c.post("/checkin", data={"nickname": "x" * 30, "code": state.code}).status_code == 200


def test_one_check_in_per_device(app):
    _open(app)
    c = app.test_client()
    c.get(_path(_state(app)))
    assert c.post("/checkin", data={"nickname": "Fox", "code": _state(app).code}).status_code == 200
    again = c.get(_path(_state(app)))
    assert again.status_code == 409 and b"already checked in" in again.data


def test_close_then_scan_or_confirm_refused(app):
    _open(app)
    c = app.test_client()
    path = _path(_state(app))
    c.get(path)
    app.extensions["services"]["session_service"].close_session()
    assert c.post("/checkin", data={"nickname": "Fox", "code": "0000"}).status_code == 409
    assert app.test_client().get(path).status_code == 409


def test_checkin_without_token(app, client):
    assert b"There is no attendance check-in right now." in client.get("/checkin").data
    _open(app)
    assert b"Scan the QR code on the projector." in client.get("/checkin").data
