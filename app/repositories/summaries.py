"""SQL for F4 summary jobs and the job state machine (FR-4.6, FR-4.7, D34)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.db import Database, valid_row_id
from app.errors import SummaryJobRunningError


class JobStatus(str, Enum):
    """The states of a job, in the only order they can be visited. The values are stored in SQLite."""

    QUEUED = "queued"
    EXTRACTING = "extracting_audio"
    TRANSCRIBING = "transcribing"
    SUMMARISING = "summarising"
    DONE = "done"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        return self in (JobStatus.DONE, JobStatus.FAILED)

    def can_move_to(self, target: "JobStatus") -> bool:
        """Single source of the transition rule: one step forward, or `failed` from any non-terminal state."""
        if self.is_terminal():
            return False
        if target is JobStatus.FAILED:
            return True
        order = _FORWARD_ORDER
        return order.index(target) == order.index(self) + 1 if target in order else False

    def label(self) -> str:
        """Plain words for the status page (D23)."""
        return _LABELS[self]


_FORWARD_ORDER = [JobStatus.QUEUED, JobStatus.EXTRACTING, JobStatus.TRANSCRIBING,
                  JobStatus.SUMMARISING, JobStatus.DONE]
_LABELS = {
    JobStatus.QUEUED: "Waiting to start",
    JobStatus.EXTRACTING: "Extracting the audio",
    JobStatus.TRANSCRIBING: "Transcribing the lecture",
    JobStatus.SUMMARISING: "Writing the summary",
    JobStatus.DONE: "Summary ready",
    JobStatus.FAILED: "Failed",
}


@dataclass(frozen=True)
class SummaryJob:
    """Snapshot of one `summary_job` row. Never holds a transcript or a file name (FR-4.5)."""

    id: int
    status: JobStatus
    progress: float
    summary_language: Optional[str]
    detected_language: Optional[str]
    media_seconds: Optional[float]
    summary_text: Optional[str]
    error_message: Optional[str]
    created_at: float
    updated_at: float
    finished_at: Optional[float]

    def is_finished(self) -> bool:
        return self.status.is_terminal()


class SummaryRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _load(row: Optional[sqlite3.Row]) -> Optional[SummaryJob]:
        if row is None:
            return None
        return SummaryJob(
            id=row["id"], status=JobStatus(row["status"]), progress=row["progress"],
            summary_language=row["summary_language"], detected_language=row["detected_language"],
            media_seconds=row["media_seconds"], summary_text=row["summary_text"],
            error_message=row["error_message"], created_at=row["created_at"],
            updated_at=row["updated_at"], finished_at=row["finished_at"],
        )

    def create(self, summary_language: Optional[str], now: float) -> SummaryJob:
        """Insert a `queued` job; raise SummaryJobRunningError if another job is active."""
        try:
            with self._db.transaction() as conn:
                if conn.execute("SELECT 1 FROM summary_job WHERE is_active = 1").fetchone():
                    raise SummaryJobRunningError()
                job_id = conn.execute(
                    "INSERT INTO summary_job(status, summary_language, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?)", (JobStatus.QUEUED.value, summary_language, now, now),
                ).lastrowid
        except sqlite3.IntegrityError as error:  # the unique index caught a race the check above missed
            raise SummaryJobRunningError() from error
        return self.get(job_id)

    def get(self, job_id: int) -> Optional[SummaryJob]:
        if not valid_row_id(job_id):
            return None  # same answer as any unknown id
        return self._load(self._db.conn().execute("SELECT * FROM summary_job WHERE id = ?", (job_id,)).fetchone())

    def active(self) -> Optional[SummaryJob]:
        return self._load(self._db.conn().execute("SELECT * FROM summary_job WHERE is_active = 1").fetchone())

    def recent(self, limit: int) -> list[SummaryJob]:
        rows = self._db.conn().execute("SELECT * FROM summary_job ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._load(row) for row in rows]

    def move(self, job_id: int, status: JobStatus, now: float) -> None:
        """Advance a running job one step. An illegal move is a programming error (ValueError).

        Terminal states are reached only through `finish` and `fail`, which also set `is_active`.
        A job that already ended is left alone (a late call must not revive it).
        """
        if status.is_terminal():
            raise ValueError("use finish() or fail() to end a job")
        with self._db.transaction() as conn:
            row = conn.execute("SELECT status FROM summary_job WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return
            current = JobStatus(row["status"])
            if current.is_terminal():
                return
            if not current.can_move_to(status):
                raise ValueError(f"illegal job move {current.value} -> {status.value}")
            conn.execute("UPDATE summary_job SET status = ?, updated_at = ? WHERE id = ?",
                         (status.value, now, job_id))

    def set_progress(self, job_id: int, progress: float, now: float) -> None:
        clamped = min(1.0, max(0.0, progress))
        self._db.conn().execute(
            "UPDATE summary_job SET progress = ?, updated_at = ? WHERE id = ? AND is_active = 1",
            (clamped, now, job_id))

    def finish(self, job_id: int, summary_text: str, detected_language: Optional[str],
               media_seconds: float, now: float) -> None:
        self._db.conn().execute(
            "UPDATE summary_job SET status = ?, is_active = 0, progress = 1.0, summary_text = ?, "
            "detected_language = ?, media_seconds = ?, updated_at = ?, finished_at = ? "
            "WHERE id = ? AND is_active = 1",
            (JobStatus.DONE.value, summary_text, detected_language, media_seconds, now, now, job_id))

    def fail(self, job_id: int, message: str, now: float) -> None:
        """End a running job as failed; a job already `done` or `failed` is unchanged."""
        self._db.conn().execute(
            "UPDATE summary_job SET status = ?, is_active = 0, error_message = ?, updated_at = ?, "
            "finished_at = ? WHERE id = ? AND is_active = 1",
            (JobStatus.FAILED.value, message, now, now, job_id))

    def fail_all_active(self, message: str, now: float) -> int:
        """Mark every running job failed (start-up recovery). Returns how many there were."""
        cursor = self._db.conn().execute(
            "UPDATE summary_job SET status = ?, is_active = 0, error_message = ?, updated_at = ?, "
            "finished_at = ? WHERE is_active = 1",
            (JobStatus.FAILED.value, message, now, now))
        return cursor.rowcount
