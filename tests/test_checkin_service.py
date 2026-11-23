"""CheckInService: one test per refusal of SD-2, plus the success paths (D30, D31)."""
import pytest

from app.errors import (
    AlreadyCheckedInError,
    EmptyNicknameError,
    OffCampusError,
    QrExpiredError,
    SessionClosedError,
    TooManyAttemptsError,
    WindowExpiredError,
    WrongCodeError,
)

IP = "10.1.2.3"
DEV = "device-a"


@pytest.fixture
def svc(app):
    services = app.extensions["services"]
    services["settings"].replace_values("campus_range", ["10.0.0.0/8"])
    return services


@pytest.fixture
def session(svc):
    return svc["session_service"].open_session()


def qr(svc, session):
    return svc["session_service"]._credentials.qr_token(session.id)


def code(svc, session):
    return svc["session_service"]._credentials.current_code(session.id)


def wrong(svc, session):
    good = code(svc, session)
    return next(c for c in ("000", "001") if c != good)


def start(svc, session, device=DEV, ip=IP):
    return svc["checkin_service"].start(qr(svc, session), device, ip)


def confirm(svc, session, c=None, nick="Fox", device=DEV, ip=IP):
    return svc["checkin_service"].confirm(device, ip, code(svc, session) if c is None else c, nick)


def test_first_visit_success(svc, session):
    assert start(svc, session) is None
    result = confirm(svc, session, nick="  Fox ")
    assert result.nickname == "Fox"
    assert svc["check_ins"].count_for_session(session.id) == 1
    assert svc["windows"].find(DEV) is None
    assert svc["check_ins"].nickname_of(DEV) == "Fox"


def test_returning_device_gets_nickname_and_needs_none(svc, session, clock):
    start(svc, session)
    confirm(svc, session)
    svc["session_service"].close_session()
    second = svc["session_service"].open_session()
    assert start(svc, second) == "Fox"
    assert confirm(svc, second, nick=None).nickname == "Fox"


def test_nickname_not_unique(svc, session):
    for dev in ("d1", "d2"):
        start(svc, session, dev)
        confirm(svc, session, nick="Same", device=dev)
    assert svc["check_ins"].count_for_session(session.id) == 2


def test_abandoned_window_creates_no_record(svc, session):
    start(svc, session)
    assert svc["check_ins"].count_for_session(session.id) == 0


def test_start_off_campus(svc, session):
    with pytest.raises(OffCampusError):
        start(svc, session, ip="8.8.8.8")


def test_confirm_off_campus(svc, session):
    start(svc, session)
    with pytest.raises(OffCampusError):
        confirm(svc, session, ip="8.8.8.8")


def test_qr_expired(svc, session, clock):
    token = qr(svc, session)
    clock.advance(26)
    with pytest.raises(QrExpiredError):
        svc["checkin_service"].start(token, DEV, IP)


def test_qr_tampered(svc, session):
    with pytest.raises(QrExpiredError):
        svc["checkin_service"].start("garbage", DEV, IP)


def test_start_closed_session(svc, session):
    token = qr(svc, session)
    svc["session_service"].close_session()
    with pytest.raises(SessionClosedError):
        svc["checkin_service"].start(token, DEV, IP)


def test_start_already_checked_in(svc, session):
    start(svc, session)
    confirm(svc, session)
    with pytest.raises(AlreadyCheckedInError):
        start(svc, session)


def test_window_at_60s_accepted(svc, session, clock):
    start(svc, session)
    clock.advance(60)
    assert confirm(svc, session).nickname == "Fox"


def test_window_at_60_001s_rejected(svc, session, clock):
    start(svc, session)
    clock.advance(60.001)
    with pytest.raises(WindowExpiredError):
        confirm(svc, session)


def test_other_device_token_rejected(svc, session):
    start(svc, session)
    with pytest.raises(WindowExpiredError):
        confirm(svc, session, device="device-b")


def test_confirm_session_closed_meanwhile(svc, session):
    start(svc, session)
    svc["session_service"].close_session()
    with pytest.raises(SessionClosedError):
        confirm(svc, session)


@pytest.mark.parametrize("nick", [None, "", "   ", "x" * 31])
def test_bad_nickname_not_counted_as_attempt(svc, session, nick):
    start(svc, session)
    with pytest.raises(EmptyNicknameError):
        confirm(svc, session, nick=nick)
    assert svc["windows"].find(DEV).attempts == 0


def test_nickname_30_chars_accepted(svc, session):
    start(svc, session)
    assert len(confirm(svc, session, nick="x" * 30).nickname) == 30


def test_wrong_code_counts_attempt_and_persists(svc, session):
    start(svc, session)
    with pytest.raises(WrongCodeError):
        confirm(svc, session, c=wrong(svc, session))
    assert svc["windows"].find(DEV).attempts == 1
    assert svc["check_ins"].nickname_of(DEV) is None  # nickname saved only on success


def test_previous_code_accepted(svc, session, clock):
    start(svc, session)
    old = code(svc, session)
    clock.advance(5)
    assert confirm(svc, session, c=old).nickname == "Fox"


def test_sixth_attempt_rejected_even_when_right(svc, session):
    start(svc, session)
    for _ in range(5):
        with pytest.raises(WrongCodeError):
            confirm(svc, session, c=wrong(svc, session))
    with pytest.raises(TooManyAttemptsError):
        confirm(svc, session)
    assert svc["windows"].find(DEV) is None
    with pytest.raises(WindowExpiredError):
        confirm(svc, session)


def test_fifth_attempt_with_right_code_succeeds(svc, session):
    start(svc, session)
    for _ in range(4):
        with pytest.raises(WrongCodeError):
            confirm(svc, session, c=wrong(svc, session))
    assert confirm(svc, session).nickname == "Fox"


def test_new_scan_resets_attempts(svc, session):
    start(svc, session)
    with pytest.raises(WrongCodeError):
        confirm(svc, session, c=wrong(svc, session))
    start(svc, session)
    assert svc["windows"].find(DEV).attempts == 0
