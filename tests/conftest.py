"""Shared fixtures. Only fictitious values; no network, no API key."""
import pytest

from app import create_app
from app.config import Config
from tests.fakes import FakeClock


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        lecturer_pin="1234",
        secret_key="test-secret-key",
        base_url="https://test.example",
        database_path=str(tmp_path / "test.db"),
    )


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(1_000_000.0)


@pytest.fixture
def app(config, clock):
    return create_app(config, clock=clock)


@pytest.fixture
def client(app):
    return app.test_client()
