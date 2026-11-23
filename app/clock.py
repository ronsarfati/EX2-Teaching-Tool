"""Time port: every timed rule (QR slots, windows) reads time here so tests can control it (D25)."""
from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    """Gives the current time as epoch seconds."""

    def now(self) -> float: ...


class SystemClock:
    """Real wall-clock time."""

    def now(self) -> float:
        return time.time()
