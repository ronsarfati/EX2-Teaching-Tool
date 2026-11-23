"""SessionService: open, close, current (FR-1.1, FR-1.13, D27)."""
import pytest

from app.errors import SessionAlreadyOpenError


@pytest.fixture
def service(app):
    return app.extensions["services"]["session_service"]


def test_current_is_none_at_start(service):
    assert service.current() is None


def test_open_creates_open_session_with_clock_time(service, clock):
    session = service.open_session()
    assert session.is_open() and session.opened_at == clock.now()
    assert service.current().id == session.id


def test_second_open_refused(service):
    service.open_session()
    with pytest.raises(SessionAlreadyOpenError):
        service.open_session()


def test_close_then_open_again(service, clock):
    first = service.open_session()
    clock.advance(60)
    service.close_session()
    assert service.current() is None
    assert service._sessions.get(first.id).closed_at == clock.now()
    assert service.open_session().id != first.id


def test_close_without_session_is_noop(service):
    service.close_session()
    assert service.current() is None
