"""Shared fixtures. Only fictitious values; no network, no API key."""
import pytest

from app import create_app
from app.config import Config
from tests.fakes import FakeAudioExtractor, FakeClock, FakeTranscriber, InlineJobRunner


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        lecturer_pin="1234",
        secret_key="test-secret-key",
        base_url="https://test.example",
        database_path=str(tmp_path / "test.db"),
        video_work_dir=str(tmp_path / "video-work"),  # never the real temp folder
    )


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(1_000_000.0)


@pytest.fixture
def app(config, clock):
    # F4 doubles by default: no ffmpeg, no Whisper model, no thread in the tests.
    return create_app(config, clock=clock, transcriber=FakeTranscriber(),
                      audio_extractor=FakeAudioExtractor(), job_runner=InlineJobRunner())


@pytest.fixture
def client(app):
    return app.test_client()
