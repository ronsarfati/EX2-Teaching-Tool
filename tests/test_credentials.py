"""T3: RotatingCredentials (QR token 10 s / accepted <= 15 s, 3-digit code 5 s)."""
import random

import pytest

from app.errors import QrExpiredError
from app.services.credentials import RotatingCredentials
from tests.fakes import FakeClock

T0 = 1_000_000.0  # multiple of 10 and 5: a slice start


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(T0)


@pytest.fixture
def creds(clock) -> RotatingCredentials:
    return RotatingCredentials("test-key", clock)


def test_qr_stable_within_slice_and_changes_next(creds, clock):
    first = creds.qr_token(1)
    clock.set(T0 + 9.999)
    assert creds.qr_token(1) == first
    clock.set(T0 + 10)
    assert creds.qr_token(1) != first


def test_verify_returns_session_id(creds):
    assert creds.verify_qr(creds.qr_token(1)) == 1


def test_random_keys_and_sessions_all_verify():
    rng = random.Random(7)
    for _ in range(2000):
        clock = FakeClock(rng.uniform(1e6, 2e9))
        c = RotatingCredentials(f"k{rng.random()}", clock)
        sid = rng.randint(1, 10**6)
        assert c.verify_qr(c.qr_token(sid)) == sid


def test_qr_age_boundary_15s(creds, clock):
    token = creds.qr_token(1)
    clock.set(T0 + 15.0)
    assert creds.verify_qr(token) == 1
    clock.set(T0 + 15.001)
    with pytest.raises(QrExpiredError):
        creds.verify_qr(token)


def test_qr_age_counts_from_slice_start(creds, clock):
    clock.set(T0 + 9.9)
    token = creds.qr_token(1)
    clock.set(T0 + 15.001)
    with pytest.raises(QrExpiredError):
        creds.verify_qr(token)


def test_qr_errors_use_srs_message(creds):
    token = creds.qr_token(1)
    swapped = "B" if token[5] != "B" else "C"
    bad = [
        token[:5] + swapped + token[6:],
        RotatingCredentials("other-key", FakeClock(T0)).qr_token(1),
        token[:-4],
        "abc",
        "",
    ]
    for value in bad:
        with pytest.raises(QrExpiredError) as info:
            creds.verify_qr(value)
        assert str(info.value) == "This QR code has expired. Scan a fresh one."


def test_code_is_three_digits_for_2000_slices(creds, clock):
    for i in range(2000):
        clock.set(T0 + i * 5)
        code = creds.current_code(1)
        assert len(code) == 3 and code.isdigit()


def test_code_stable_within_slice(creds, clock):
    first = creds.current_code(1)
    clock.set(T0 + 4.999)
    assert creds.current_code(1) == first


def test_code_current_and_previous_accepted_older_rejected(creds, clock):
    old = creds.current_code(1)
    clock.set(T0 + 5)
    assert creds.is_valid_code(1, creds.current_code(1))
    assert creds.is_valid_code(1, old)
    clock.set(T0 + 10)
    # a 1-in-1000 collision with a newer slice is possible: pick a start whose codes differ
    while old in (creds.current_code(1), creds._code_for_slice(1, int(clock.now()) // 5 - 1)):
        clock.advance(5)
        old = creds._code_for_slice(1, int(clock.now()) // 5 - 2)
    assert not creds.is_valid_code(1, old)


def test_wrong_and_malformed_codes_rejected(creds):
    valid = {creds.current_code(1), creds._code_for_slice(1, int(T0) // 5 - 1)}
    wrong = next(f"{n:03d}" for n in range(1000) if f"{n:03d}" not in valid)
    assert not creds.is_valid_code(1, wrong)
    for bad in ("12", "1234", "12a", "", "١٢٣"):
        assert not creds.is_valid_code(1, bad)


def test_code_depends_on_session(creds):
    codes = {creds.current_code(s) for s in range(1, 30)}
    assert len(codes) > 1
