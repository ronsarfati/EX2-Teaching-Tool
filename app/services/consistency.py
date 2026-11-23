"""D7 consistency rule between check-ins (N) and faces counted on the photo (D). Pure, no dependency."""
from __future__ import annotations

from dataclasses import dataclass

MIN_MISSING = 7  # faces that may be missing: absent from the photo (turned away, hidden) ...
MISSING_RATIO_PERCENT = 15  # ... or 15 % of N, whichever is larger
MIN_EXTRA = 4  # faces that may be in excess: non-students, false detections ...
EXTRA_RATIO_PERCENT = 10  # ... or 10 % of N


def _ceil_percent(n: int, percent: int) -> int:
    """ceil(n * percent / 100) in integers: a float ceil could be off by one on exact multiples."""
    return -(-n * percent // 100)


@dataclass(frozen=True)
class ConsistencyResult:
    """Outcome of comparing N and D (FR-1.16)."""

    n: int
    d: int
    lower: int
    upper: int

    @property
    def consistent(self) -> bool:
        return self.lower <= self.d <= self.upper

    def label(self) -> str:
        return "consistent" if self.consistent else "anomaly"

    @staticmethod
    def evaluate(n: int, d: int) -> "ConsistencyResult":
        lower = n - max(MIN_MISSING, _ceil_percent(n, MISSING_RATIO_PERCENT))
        upper = n + max(MIN_EXTRA, _ceil_percent(n, EXTRA_RATIO_PERCENT))
        return ConsistencyResult(n, d, lower, upper)
