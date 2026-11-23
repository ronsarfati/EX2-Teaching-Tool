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
