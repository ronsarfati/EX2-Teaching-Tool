"""T18b minimal tests: ffmpeg extractor, faster-whisper adapter (fake module), thread runner. Offline."""
import subprocess
import sys
import threading
import types

import pytest

from app.adapters.audio import FfmpegAudioExtractor
from app.adapters.jobs import ThreadJobRunner
from app.adapters.transcriber import FasterWhisperTranscriber
from app.errors import TranscriptionUnavailableError, UnreadableVideoError, VideoTooLongError


def _run_stub(monkeypatch, *, returncode=0, write=100, raises=None):
    captured = {}

    def run(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        if raises:
            raise raises
        with open(command[-1], "wb") as out:
            out.write(bytes(write))
        return subprocess.CompletedProcess(command, returncode, b"", b"boom")

    monkeypatch.setattr(subprocess, "run", run)
    return captured


def test_ffmpeg_command_is_an_argument_list(monkeypatch, tmp_path):
    captured = _run_stub(monkeypatch)
    FfmpegAudioExtractor().extract(tmp_path / "input.mp4", tmp_path / "audio.wav")
    assert captured["command"][:2] == ["ffmpeg", "-nostdin"]
    assert captured["command"][captured["command"].index("-map") + 1] == "0:a:0"
    assert "-ar" in captured["command"] and "16000" in captured["command"]
    assert not captured["kwargs"].get("shell") and captured["kwargs"]["timeout"] == 1800


@pytest.mark.parametrize("kwargs, error", [
    ({"returncode": 1}, UnreadableVideoError),
    ({"write": 44}, UnreadableVideoError),
    ({"raises": subprocess.TimeoutExpired("ffmpeg", 1)}, VideoTooLongError),
    ({"raises": FileNotFoundError()}, TranscriptionUnavailableError),
])
def test_ffmpeg_failures(monkeypatch, tmp_path, kwargs, error):
    _run_stub(monkeypatch, **kwargs)
    with pytest.raises(error):
        FfmpegAudioExtractor().extract(tmp_path / "input.mp4", tmp_path / "audio.wav")


class _Model:
    loads = []
    fail = False

    def __init__(self, size, device, compute_type):
        if _Model.fail:
            raise OSError("no network")
        _Model.loads.append((size, device, compute_type))

    def transcribe(self, path, **kwargs):
        _Model.kwargs = kwargs
        segments = [types.SimpleNamespace(text=" one ", end=5.0), types.SimpleNamespace(text="two", end=10.0)]
        return iter(segments), types.SimpleNamespace(language="he", duration=10.0)


@pytest.fixture
def fake_whisper(monkeypatch):
    _Model.loads, _Model.fail = [], False
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_Model))
    return _Model


def test_transcriber_loads_lazily_once_and_reports_progress(fake_whisper, tmp_path):
    transcriber = FasterWhisperTranscriber("small", "he")
    assert fake_whisper.loads == []
    seen = []
    transcript = transcriber.transcribe(tmp_path / "a.wav", seen.append)
    transcriber.transcribe(tmp_path / "a.wav")
    assert fake_whisper.loads == [("small", "cpu", "int8")]
    assert fake_whisper.kwargs == {"language": "he", "beam_size": 1, "vad_filter": True}
    assert seen == [0.5, 1.0]
    assert (transcript.text, transcript.language, transcript.duration_s) == ("one\ntwo", "he", 10.0)


def test_model_failure_is_not_cached(fake_whisper, tmp_path):
    transcriber = FasterWhisperTranscriber("small", None)
    fake_whisper.fail = True
    with pytest.raises(TranscriptionUnavailableError):
        transcriber.transcribe(tmp_path / "a.wav")
    fake_whisper.fail = False
    assert transcriber.transcribe(tmp_path / "a.wav").text == "one\ntwo"


def test_thread_runner_uses_a_named_daemon_thread():
    seen, done = {}, threading.Event()

    def task():
        thread = threading.current_thread()
        seen.update(name=thread.name, daemon=thread.daemon, main=thread is threading.main_thread())
        done.set()

    ThreadJobRunner().submit(task)
    assert done.wait(5)
    assert seen == {"name": "video-summary-job", "daemon": True, "main": False}
