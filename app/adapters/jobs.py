"""Background job port and its thread adapter (F4, FR-4.6, D34)."""
from __future__ import annotations

import threading
from typing import Callable, Protocol


class JobRunner(Protocol):
    """Run a task outside the web request."""

    def submit(self, task: Callable[[], None]) -> None: ...


class ThreadJobRunner:
    """One daemon thread per task: no pool and no queue, because the repository allows one active job only."""

    def submit(self, task: Callable[[], None]) -> None:
        # Daemon: the thread dies with the process; the next start cleans up (recover_interrupted).
        threading.Thread(target=task, name="video-summary-job", daemon=True).start()
