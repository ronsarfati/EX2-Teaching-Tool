"""T3 extra tests: RotatingCredentials edge cases. Covers D30, D31 (QR 10 s / <= 15 s, code 5 s, current or previous)."""
import random

import pytest

from app.errors import QrExpiredError
from app.services.credentials import RotatingCredentials
from tests.fakes import FakeClock

T0 = 1_000_000.0  # multiple of 10 and 5


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(T0)


@pytest.fixture
def creds(clock) -> RotatingCredentials:
    return RotatingCredentials("test-key", clock)


def _find_session_with_distinct_codes(creds, clock, n=3):
    """Return a session id whose codes for n consecutive slices are pairwise distinct."""
    for sid in range(1, 200):
        codes = []
        for i in range(n):
            clock.set(T0 + 5 * i)
            codes.append(creds.current_code(sid))
        if len(set(codes)) == n:
            clock.set(T0)
            return sid
    raise AssertionError("no session with distinct codes")


@pytest.mark.parametrize("bad", ["١٢٣", "１２３", "   ", " 12", "12 ", "12", "1234", "", "abc", "-12", "1.5", "12\n", "²³¹"])
def test_invalid_code_strings_rejected(creds, bad):
    """Covers D30: non-ASCII digits, whitespace, wrong length rejected."""
    assert creds.is_valid_code(1, bad) is False


def test_none_code_rejected_without_crash(creds):
    """Covers D30: None never validates (rejected or TypeError-free)."""
    try:
        assert creds.is_valid_code(1, None) is False
    except TypeError:
        pytest.fail("is_valid_code(None) raised TypeError (spec: never raises)")


def test_code_always_four_zero_padded_digits(creds, clock):
    """Covers D30: 4 chars, zero-padded, over many slices."""
    seen_leading_zero = False
    for i in range(3000):
        clock.set(T0 + 5 * i)
        code = creds.current_code(7)
        assert len(code) == 4 and code.isascii() and code.isdigit()
        seen_leading_zero |= code.startswith("0")
        assert creds.is_valid_code(7, code)
    assert seen_leading_zero


def test_code_stable_within_slice(creds, clock):
    c = creds.current_code(1)
    clock.set(T0 + 4.999)
    assert creds.current_code(1) == c


def test_previous_slice_accepted_but_not_previous_previous(creds, clock):
    """Covers D30: exactly current and previous slice accepted, at slice edges."""
    sid = _find_session_with_distinct_codes(creds, clock, 3)
    clock.set(T0)
    c0 = creds.current_code(sid)  # slice [T0, T0+5)
    clock.set(T0 + 5)
    c1 = creds.current_code(sid)
    clock.set(T0 + 10)
    c2 = creds.current_code(sid)
    assert len({c0, c1, c2}) == 3

    # t = 5.0 : current c1, previous c0
    clock.set(T0 + 5.0)
    assert creds.is_valid_code(sid, c1) and creds.is_valid_code(sid, c0)
    # t = 9.999 : still slice 1, c0 still previous
    clock.set(T0 + 9.999)
    assert creds.is_valid_code(sid, c1) and creds.is_valid_code(sid, c0)
    # t = 10.0 : c0 is previous-previous -> rejected; c1 previous, c2 current
    clock.set(T0 + 10.0)
    assert creds.is_valid_code(sid, c2) and creds.is_valid_code(sid, c1)
    assert not creds.is_valid_code(sid, c0)
    # t = 14.999 and 15.0 : c1 previous until 15
    clock.set(T0 + 14.999)
    assert creds.is_valid_code(sid, c1)
    clock.set(T0 + 15.0)
    assert not creds.is_valid_code(sid, c1)


def test_future_code_rejected(creds, clock):
    sid = _find_session_with_distinct_codes(creds, clock, 3)
    clock.set(T0 + 5)
    nxt_clock_code = None
    clock.set(T0 + 10)
    nxt_clock_code = creds.current_code(sid)
    clock.set(T0)
    assert not creds.is_valid_code(sid, nxt_clock_code)


def test_qr_boundaries_exact(creds, clock):
    """Covers D31: 15.000 s accepted, 15.001 rejected."""
    token = creds.qr_token(3)
    clock.set(T0 + 15.0)
    assert creds.verify_qr(token) == 3
    clock.set(T0 + 15.001)
    with pytest.raises(QrExpiredError):
        creds.verify_qr(token)


def test_future_token_rejected(clock):
    """Covers D31: a token created later than 'now' (age < 0) is rejected."""
    other = RotatingCredentials("test-key", FakeClock(T0 + 60))
    token = other.qr_token(1)
    c = RotatingCredentials("test-key", clock)
    with pytest.raises(QrExpiredError):
        c.verify_qr(token)


def test_token_of_other_session_returns_its_own_session(creds):
    """Token embeds its session: verifying yields that session, never another."""
    t1, t2 = creds.qr_token(1), creds.qr_token(2)
    assert t1 != t2
    assert creds.verify_qr(t1) == 1
    assert creds.verify_qr(t2) == 2
    assert creds.verify_qr(t1) != 2


def test_tampered_session_in_token_rejected(creds):
    """Swapping the session id inside a token must break the signature."""
    import base64
    raw = base64.urlsafe_b64decode(creds.qr_token(1) + "==")
    forged = raw.replace(b"1|", b"2|", 1)
    tok = base64.urlsafe_b64encode(forged).decode().rstrip("=")
    with pytest.raises(QrExpiredError):
        creds.verify_qr(tok)


def test_codes_differ_between_sessions(creds):
    codes = {creds.current_code(s) for s in range(1, 40)}
    assert len(codes) > 10


def test_session_code_not_valid_for_other_session(creds):
    """A code for session A is rejected for session B (except for a 1/500 collision, so pick a pair)."""
    for b in range(2, 50):
        if creds.current_code(1) != creds.current_code(b) and creds.current_code(1) != _prev(creds, b):
            assert not creds.is_valid_code(b, creds.current_code(1))
            return
    pytest.fail("no non-colliding pair")


def _prev(creds, sid):
    clock = creds._clock
    now = clock.now()
    clock.set(now - 5)
    p = creds.current_code(sid)
    clock.set(now)
    return p


def test_different_secret_rejects_token_and_codes(clock):
    a = RotatingCredentials("key-A", clock)
    b = RotatingCredentials("key-B", clock)
    with pytest.raises(QrExpiredError):
        b.verify_qr(a.qr_token(1))
    assert a.verify_qr(a.qr_token(1)) == 1
    differing = sum(a.current_code(s) != b.current_code(s) for s in range(1, 50))
    assert differing > 40


@pytest.mark.parametrize("junk", ["", "!!!", "abc", "AAAA", "a" * 500, "é", "\x00", "MXwx"])
def test_garbage_tokens_raise_qr_expired(creds, junk):
    with pytest.raises(QrExpiredError):
        creds.verify_qr(junk)


def test_2000_tokens_regression_roundtrip_and_expiry():
    """2,000 random tokens: valid at age <= 15, rejected at age > 15 (guards the b'|' in signature bug)."""
    rng = random.Random(42)
    for _ in range(2000):
        t = rng.randint(10**6, 2 * 10**9)
        clock = FakeClock(float(t))
        c = RotatingCredentials(f"k{rng.random()}", clock)
        sid = rng.randint(1, 10**6)
        token = c.qr_token(sid)
        clock.set(t + rng.uniform(0, 5))
        assert c.verify_qr(token) == sid
        clock.set(t + 25)
        with pytest.raises(QrExpiredError):
            c.verify_qr(token)
