"""Test doubles of the ports (not production code)."""
from __future__ import annotations

from pathlib import Path


class FakeClock:
    """Clock whose time only moves when the test says so (D25)."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def set(self, t: float) -> None:
        self._now = t

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeHeadCounter:
    """HeadCounter that returns a preset count, or raises a preset error; remembers what it was given."""

    def __init__(self, count: int = 0, error: Exception | None = None) -> None:
        self.count = count
        self.error = error
        self.received: list[bytes] = []

    def count_faces(self, image: bytes) -> int:
        self.received.append(image)
        if self.error is not None:
            raise self.error
        return self.count


class FakeLLMClient:
    """LLMClient returning a preset text (or a function of the prompt), or raising a preset error; records calls."""

    def __init__(self, reply="OK", error: Exception | None = None, configured: bool = True) -> None:
        self.reply = reply
        self.error = error
        self.configured = configured
        self.calls: list[dict] = []

    def is_configured(self) -> bool:
        return self.configured

    def complete(self, system: str, prompt: str, max_tokens: int, feature: str = "review") -> str:
        self.calls.append({"system": system, "prompt": prompt, "max_tokens": max_tokens})
        if self.error is not None:
            raise self.error
        return self.reply(prompt) if callable(self.reply) else self.reply


class FakeRepoFetcher:
    """RepoFetcher serving preset extracts by canonical URL; unknown URLs are unavailable. Records fetch calls."""

    def __init__(self, repos: dict | None = None) -> None:
        self.repos = repos or {}
        self.calls: list[tuple[str, int]] = []

    def normalize_url(self, url: str) -> str:
        from app.adapters.repo_fetcher import GitHubRepoFetcher
        return GitHubRepoFetcher().normalize_url(url)

    def fetch(self, url: str, max_chars: int):
        from app.errors import RepoUnavailableError
        canonical = self.normalize_url(url)
        self.calls.append((canonical, max_chars))
        if canonical not in self.repos:
            raise RepoUnavailableError()
        return self.repos[canonical]


class FakeAudioExtractor:
    """AudioExtractor writing a small dummy WAV, or raising a preset error; remembers what it saw."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[Path, Path]] = []
        self.input_existed: list[bool] = []

    def extract(self, media_path: Path, wav_path: Path) -> None:
        self.calls.append((media_path, wav_path))
        self.input_existed.append(media_path.exists())
        if self.error is not None:
            raise self.error
        wav_path.write_bytes(b"RIFF" + bytes(100))


class FakeTranscriber:
    """Transcriber returning a preset Transcript (progress 0.25, 0.5, 1.0), or raising a preset error.

    `on_call` is an optional hook run at the start of each call, so a test can observe the job status.
    """

    def __init__(self, transcript=None, error: Exception | None = None, on_call=None) -> None:
        from app.adapters.transcriber import Transcript
        self.transcript = transcript or Transcript("Today we study classes and objects.", "en", 60.0)
        self.error = error
        self.on_call = on_call
        self.calls: list[Path] = []
        self.audio_existed: list[bool] = []

    def transcribe(self, audio_path: Path, on_progress=None):
        self.calls.append(audio_path)
        self.audio_existed.append(audio_path.exists())
        if self.on_call is not None:
            self.on_call()
        if self.error is not None:
            raise self.error
        for fraction in (0.25, 0.5, 1.0):
            if on_progress is not None:
                on_progress(fraction)
        return self.transcript


class InlineJobRunner:
    """JobRunner that runs the task at once, in the calling thread (deterministic tests)."""

    def submit(self, task) -> None:
        task()


class DeferredJobRunner:
    """JobRunner that keeps the tasks until `run_all()`, to observe a `queued` job."""

    def __init__(self) -> None:
        self.tasks: list = []

    def submit(self, task) -> None:
        self.tasks.append(task)

    def run_all(self) -> None:
        tasks, self.tasks = self.tasks, []
        for task in tasks:
            task()
