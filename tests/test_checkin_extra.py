"""CheckInService extra boundaries and persistence rules (SD-2, SD-2b, D30, D31). FakeClock only."""
import pytest

from app.errors import (
    AlreadyCheckedInError,
    EmptyNicknameError,
    QrExpiredError,
    SessionClosedError,
    TooManyAttemptsError,
    WindowExpiredError,
    WrongCodeError,
)

DEV = "device-a"


@pytest.fixture
def svc(app):
    services = app.extensions["services"]
    return services


@pytest.fixture
def session(svc):
    return svc["session_service"].open_session()


def creds(svc):
    return svc["session_service"]._credentials


def qr(svc, session):
    return creds(svc).qr_token(session.id)


def code(svc, session):
    return creds(svc).current_code(session.id)


def bad_code(svc, session):
    """A code that is neither the current nor the previous slice's code."""
    c = creds(svc)
    n = int(svc["session_service"]._credentials._clock.now()) // 5
    ok = {c._code_for_slice(session.id, n), c._code_for_slice(session.id, n - 1)}
    return next(f"{i:04d}" for i in range(10000) if f"{i:04d}" not in ok)


def start(svc, session, device=DEV):
    return svc["checkin_service"].start(qr(svc, session), device)


def confirm(svc, session, c=None, nick="Fox", device=DEV):
    return svc["checkin_service"].confirm(device, code(svc, session) if c is None else c, nick)


def test_window_60_000s_accepted(svc, session, clock):
    """Covers FR-1.6, D31: window boundary."""
    start(svc, session)
    clock.advance(60.0)
    assert confirm(svc, session).nickname == "Fox"


def test_window_60_001s_rejected(svc, session, clock):
    """Covers FR-1.6."""
    start(svc, session)
    clock.advance(60.001)
    with pytest.raises(WindowExpiredError):
        confirm(svc, session)


def test_attempts_persist_1_to_5_then_sixth_rejected_even_if_right(svc, session):
    """Covers FR-1.7, D31: counter survives the refusal."""
    start(svc, session)
    for expected in range(1, 6):
        with pytest.raises(WrongCodeError):
            confirm(svc, session, c=bad_code(svc, session))
        assert svc["windows"].find(DEV).attempts == expected
    with pytest.raises(TooManyAttemptsError):
        confirm(svc, session)
    assert svc["check_ins"].count_for_session(session.id) == 0


def test_empty_nickname_does_not_consume_attempt(svc, session):
    """Covers D31."""
    start(svc, session)
    for _ in range(3):
        with pytest.raises(EmptyNicknameError):
            confirm(svc, session, nick="")
    assert svc["windows"].find(DEV).attempts == 0
    assert confirm(svc, session).nickname == "Fox"


def test_nickname_31_rejected_30_accepted_unicode_ok(svc, session):
    """Covers FR-1.8 boundaries and unicode."""
    start(svc, session)
    with pytest.raises(EmptyNicknameError):
        confirm(svc, session, nick="y" * 31)
    assert confirm(svc, session, nick="y" * 30).nickname == "y" * 30
    start(svc, session, device="d2")
    nick = "שלום-Zoë-日本"
    assert confirm(svc, session, nick=nick, device="d2").nickname == nick
    assert svc["check_ins"].nickname_of("d2") == nick


def test_nickname_stored_only_on_success(svc, session):
    """Covers FR-1.8."""
    start(svc, session)
    with pytest.raises(WrongCodeError):
        confirm(svc, session, c=bad_code(svc, session), nick="Ghost")
    assert svc["check_ins"].nickname_of(DEV) is None
    confirm(svc, session, nick="Real")
    assert svc["check_ins"].nickname_of(DEV) == "Real"


def test_returning_device_reuses_stored_nickname_ignoring_new(svc, session):
    """Covers FR-1.8: stored nickname wins."""
    start(svc, session)
    confirm(svc, session)
    svc["session_service"].close_session()
    nxt = svc["session_service"].open_session()
    assert start(svc, nxt) == "Fox"
    assert confirm(svc, nxt, nick=None).nickname == "Fox"


def test_returning_device_ignores_other_nickname(svc, session):
    """Covers FR-1.8."""
    start(svc, session)
    confirm(svc, session)
    svc["session_service"].close_session()
    nxt = svc["session_service"].open_session()
    start(svc, nxt)
    assert confirm(svc, nxt, nick="Other").nickname == "Fox"


def test_new_scan_replaces_window_and_resets_attempts(svc, session, clock):
    """Covers FR-1.9."""
    start(svc, session)
    for _ in range(3):
        with pytest.raises(WrongCodeError):
            confirm(svc, session, c=bad_code(svc, session))
    clock.advance(50)
    start(svc, session)
    w = svc["windows"].find(DEV)
    assert w.attempts == 0 and w.opened_at == clock.now()
    clock.advance(55)  # would be expired for the first window
    assert confirm(svc, session).nickname == "Fox"


def test_other_device_token_rejected(svc, session):
    """Covers FR-1.6."""
    start(svc, session)
    with pytest.raises(WindowExpiredError):
        confirm(svc, session, device="other")
    assert svc["windows"].find(DEV) is not None


def test_session_closed_between_start_and_confirm(svc, session):
    """Covers FR-1.2, SD-2b."""
    start(svc, session)
    svc["session_service"].close_session()
    with pytest.raises(SessionClosedError):
        confirm(svc, session)
    assert svc["check_ins"].count_for_session(session.id) == 0


def test_qr_15_000_accepted_15_001_rejected_at_start(svc, session, clock):
    """Covers FR-1.3, D31."""
    token = qr(svc, session)
    clock.advance(15.0)
    assert svc["checkin_service"].start(token, DEV) is None
    clock.advance(0.001)
    with pytest.raises(QrExpiredError):
        svc["checkin_service"].start(token, "d2")


def test_one_check_in_per_device_per_session(svc, session):
    """Covers FR-1.10."""
    start(svc, session)
    confirm(svc, session)
    with pytest.raises(AlreadyCheckedInError):
        start(svc, session)
    assert svc["check_ins"].count_for_session(session.id) == 1


def test_same_device_can_check_in_next_session(svc, session):
    """Covers FR-1.10."""
    start(svc, session)
    confirm(svc, session)
    svc["session_service"].close_session()
    nxt = svc["session_service"].open_session()
    start(svc, nxt)
    confirm(svc, nxt, nick=None)
    assert svc["check_ins"].count_for_session(nxt.id) == 1


def test_code_previous_slice_accepted(svc, session, clock):
    """Covers FR-1.5, P1."""
    start(svc, session)
    old = code(svc, session)
    clock.advance(5)
    assert confirm(svc, session, c=old).nickname == "Fox"


def test_code_two_slices_old_rejected(svc, session, clock):
    """Covers FR-1.5, P1."""
    start(svc, session)
    old = code(svc, session)
    c = creds(svc)
    clock.advance(10)
    n = int(clock.now()) // 5
    if old in {c._code_for_slice(session.id, n), c._code_for_slice(session.id, n - 1)}:
        pytest.skip("4-digit collision with a valid code")
    with pytest.raises(WrongCodeError):
        confirm(svc, session, c=old)
