"""Display time zone (D35): times are stored as UTC epoch seconds and shown in Israel local time.

Only the display changes; the database and the Clock stay in UTC. The zone is a constant rather than a
setting because the course runs in one place; `tzdata` provides the zone database on Windows and in containers.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

DISPLAY_TIMEZONE = "Asia/Jerusalem"
ZONE_LABEL = "Jerusalem time"  # shown in spreadsheet headers so nobody reads the values as UTC
_ZONE = ZoneInfo(DISPLAY_TIMEZONE)


def to_local(timestamp: float) -> datetime:
    """Convert a UTC epoch timestamp to an aware datetime in Israel time (DST handled by the zone rules)."""
    return datetime.fromtimestamp(timestamp, tz=_ZONE)


def format_local(timestamp: float, pattern: str) -> str:
    """Format a UTC epoch timestamp in Israel time with a strftime `pattern`."""
    return to_local(timestamp).strftime(pattern)
