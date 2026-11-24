"""Simultaneous check-ins on a real temp-file SQLite DB (threads, real services, fake clock).

Covers FR-1.6-FR-1.12 (check-in), UNIQUE(session_id, device_token), D3 (BEGIN IMMEDIATE + busy_timeout).
Question answered: if many students confirm at the very same instant, are all recorded, with no 500
and no "database is locked"?
"""
import threading

import pytest

from app.errors import AlreadyCheckedInError, CheckInError, WindowExpiredError


@pytest.fixture
def svc(app):
    return app.extensions["services"]


@pytest.fixture
def session(svc):
    return svc["session_service"].open_session()


def _code(svc, session):
    return svc["session_service"]._credentials.current_code(session.id)


def _qr(svc, session):
    return svc["session_service"]._credentials.qr_token(session.id)


def _run_together(jobs):
    """Run each callable in its own thread released by one Barrier; return a list of ('ok'|'err', value)."""
    barrier = threading.Barrier(len(jobs))
    results = [None] * len(jobs)

    def runner(i, job):
        barrier.wait(timeout=10)
        try:
            results[i] = ("ok", job())
        except BaseException as exc:  # noqa: BLE001 - the test must see every kind of failure
            results[i] = ("err", exc)

    threads = [threading.Thread(target=runner, args=(i, j)) for i, j in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert all(r is not None for r in results), "a thread did not finish"
    return results


def test_50_distinct_devices_confirm_at_the_same_instant(svc, session):
    """Covers FR-1.6, D3: 50 devices confirm together -> 50 rows, 0 errors."""
    n = 50
    qr, code = _qr(svc, session), _code(svc, session)
    for i in range(n):  # every phone scanned the QR first (window open)
        svc["checkin_service"].start(qr, f"dev-{i}")
    results = _run_together(
        [lambda i=i: svc["checkin_service"].confirm(f"dev-{i}", code, f"Nick{i}") for i in range(n)]
    )
    errors = [r[1] for r in results if r[0] == "err"]
    assert errors == []
    assert svc["check_ins"].count_for_session(session.id) == n


def test_50_distinct_devices_scan_and_confirm_all_in_parallel(svc, session):
    """Covers FR-1.6, D3: scan (start) and confirm both run concurrently for 50 devices."""
    n = 50
    qr, code = _qr(svc, session), _code(svc, session)

    def full_flow(i):
        svc["checkin_service"].start(qr, f"dev-{i}")
        return svc["checkin_service"].confirm(f"dev-{i}", code, f"Nick{i}")

    results = _run_together([lambda i=i: full_flow(i) for i in range(n)])
    assert [r[1] for r in results if r[0] == "err"] == []
    assert svc["check_ins"].count_for_session(session.id) == n


def test_same_device_confirms_from_10_threads_gives_exactly_one_row(svc, session):
    """Covers FR-1.12, UNIQUE(session_id, device_token): one row; losers get a clean CheckInError, never a DB error."""
    qr, code = _qr(svc, session), _code(svc, session)
    svc["checkin_service"].start(qr, "same-dev")
    results = _run_together(
        [lambda: svc["checkin_service"].confirm("same-dev", code, "Fox") for _ in range(10)]
    )
    oks = [r for r in results if r[0] == "ok"]
    errs = [r[1] for r in results if r[0] == "err"]
    assert len(oks) == 1
    assert len(errs) == 9
    # The winner deletes the window, so the losers see "window expired"; both are user-facing CheckInErrors (4xx).
    assert all(isinstance(e, (WindowExpiredError, AlreadyCheckedInError)) for e in errs), errs
    assert all(isinstance(e, CheckInError) for e in errs)
    assert svc["check_ins"].count_for_session(session.id) == 1


def test_same_device_scan_and_confirm_from_10_threads_gives_exactly_one_row(svc, session):
    """Covers FR-1.12: the whole flow (scan then confirm) repeated by 10 tabs of one phone -> 1 row, only CheckInErrors."""
    qr, code = _qr(svc, session), _code(svc, session)

    def full_flow():
        svc["checkin_service"].start(qr, "same-dev")
        return svc["checkin_service"].confirm("same-dev", code, "Fox")

    results = _run_together([full_flow for _ in range(10)])
    errs = [r[1] for r in results if r[0] == "err"]
    assert all(isinstance(e, CheckInError) for e in errs), errs
    assert sum(1 for r in results if r[0] == "ok") == 1
    assert svc["check_ins"].count_for_session(session.id) == 1
