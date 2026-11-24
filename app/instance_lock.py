"""Single-instance guard: a second `python -m app` must not touch the database of the running one (D34)."""
from __future__ import annotations

from pathlib import Path
from typing import IO, Optional

try:
    import fcntl
except ImportError:  # Windows: no flock, the guard is skipped rather than blocking the app
    fcntl = None  # type: ignore[assignment]


class InstanceLock:
    """An exclusive, non-blocking `flock` on a file; the OS releases it when the process ends or `release` is called."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: Optional[IO[str]] = None

    def acquire(self) -> bool:
        """True if this process now holds the lock (or the platform has no flock); False if another one does."""
        if fcntl is None:
            return True
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._file = handle  # kept open for the whole process lifetime: closing it would drop the lock
        return True

    def release(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
