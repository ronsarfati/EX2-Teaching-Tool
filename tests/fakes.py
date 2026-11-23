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
