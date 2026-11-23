"""Test doubles of the ports (not production code)."""
from __future__ import annotations


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
