"""F4 video summary job (FR-4.1-FR-4.9, D34): accept one recording, process it in the background, keep only the summary.

Privacy rules enforced here (FR-4.5): media files live only in `work_root/job-<id>/` and are deleted on every
exit; the transcript is a local variable that is never written anywhere; the uploaded file name is never stored.
"""
from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import BinaryIO, Optional

from werkzeug.exceptions import NotFound

from app.adapters.audio import AudioExtractor
from app.adapters.jobs import JobRunner
from app.adapters.transcriber import Transcriber
from app.clock import Clock
from app.errors import (AppError, LLMUnavailableError, NoSpeechError, UnreadableVideoError,
                        UnsupportedVideoFormatError)
from app.repositories.summaries import JobStatus, SummaryJob, SummaryRepository
from app.services.lecture_summary import LectureSummariser
from app.timezone import format_local

_LOG = logging.getLogger(__name__)
GENERIC_MESSAGE = "Something went wrong. Please try again."
INTERRUPTED_MESSAGE = ("The summary was interrupted because the app was restarted. "
                       "Please upload the video again.")
_JOB_DIR = re.compile(r"job-\d+")  # the only directory names recovery is allowed to delete


class VideoSummaryService:
    ALLOWED_EXTENSIONS = frozenset({".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".m4a", ".mp3",
                                    ".wav", ".aac", ".ogg", ".opus", ".flac"})
    SUMMARY_LANGUAGES = ("auto", "en", "he")
    COPY_CHUNK_BYTES = 1024 * 1024  # copy in 1 MiB pieces: a 2 GB recording is never held in memory
    PROGRESS_STEP = 0.01  # write progress at most about 100 times per job

    def __init__(self, jobs: SummaryRepository, extractor: AudioExtractor, transcriber: Transcriber,
                 summariser: LectureSummariser, runner: JobRunner, clock: Clock, work_root: Path) -> None:
        self._jobs = jobs
        self._extractor = extractor
        self._transcriber = transcriber
        self._summariser = summariser
        self._runner = runner
        self._clock = clock
        self._work_root = work_root

    def submit(self, upload: BinaryIO, filename: str, language: str) -> SummaryJob:
        """Save the upload and start the background job. Nothing is written before the job row exists."""
        suffix = Path(filename or "").suffix.lower()
        if suffix not in self.ALLOWED_EXTENSIONS:  # also covers "no file" and "no extension"
            raise UnsupportedVideoFormatError()
        # "auto" and any tampered value mean "same language as the lecture" (stored as NULL).
        summary_language = language if language in self.SUMMARY_LANGUAGES and language != "auto" else None
        if not self._summariser.is_available():  # fail fast: do not copy 2 GB we could not summarise
            raise LLMUnavailableError("summary")
        job = self._jobs.create(summary_language, self._clock.now())  # raises SummaryJobRunningError
        job_dir = self._job_dir(job.id)
        media_path = job_dir / f"input{suffix}"
        try:
            job_dir.mkdir(parents=True)
            self._copy(upload, media_path)
            self._runner.submit(lambda: self._run(job.id, media_path, summary_language))
        except Exception as error:
            shutil.rmtree(job_dir, ignore_errors=True)
            message = error.user_message if isinstance(error, AppError) else GENERIC_MESSAGE
            self._jobs.fail(job.id, message, self._clock.now())
            raise
        return job

    def get(self, job_id: int) -> SummaryJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFound("This summary does not exist.")
        return job

    def active(self) -> Optional[SummaryJob]:
        return self._jobs.active()

    def recent(self, limit: int = 10) -> list[SummaryJob]:
        return self._jobs.recent(limit)

    def recover_interrupted(self) -> int:
        """At start-up no job thread exists: fail the leftover active jobs and remove their media directories."""
        count = self._jobs.fail_all_active(INTERRUPTED_MESSAGE, self._clock.now())
        if self._work_root.is_dir():
            for entry in self._work_root.iterdir():
                # Only job-<digits> folders: a misconfigured work dir must not delete unrelated files.
                if _JOB_DIR.fullmatch(entry.name) and entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry, ignore_errors=True)
        return count

    def _job_dir(self, job_id: int) -> Path:
        return self._work_root / f"job-{job_id}"

    def _copy(self, upload: BinaryIO, target: Path) -> None:
        with target.open("wb") as out:
            shutil.copyfileobj(upload, out, self.COPY_CHUNK_BYTES)
        if target.stat().st_size == 0:
            raise UnreadableVideoError()

    def _run(self, job_id: int, media_path: Path, language: Optional[str]) -> None:
        """The job body (background thread). Every exit ends in `done` or `failed` and removes the media files."""
        job_dir = media_path.parent
        try:
            self._jobs.move(job_id, JobStatus.EXTRACTING, self._clock.now())
            wav_path = job_dir / "audio.wav"
            self._extractor.extract(media_path, wav_path)
            media_path.unlink(missing_ok=True)  # the large upload goes first
            if not self._is_still_active(job_id):
                return
            self._jobs.move(job_id, JobStatus.TRANSCRIBING, self._clock.now())
            transcript = self._transcriber.transcribe(wav_path, self._progress_writer(job_id))
            shutil.rmtree(job_dir, ignore_errors=True)  # the audio is not needed any more: delete before the LLM call
            if not self._is_still_active(job_id):
                return
            if not transcript.text.strip():
                raise NoSpeechError()
            self._jobs.move(job_id, JobStatus.SUMMARISING, self._clock.now())
            text = self._summariser.summarise(transcript, language)
            self._jobs.finish(job_id, text, transcript.language, transcript.duration_s, self._clock.now())
        except AppError as error:
            self._jobs.fail(job_id, error.user_message, self._clock.now())
        except Exception:  # noqa: BLE001 - a background thread must never die silently
            _LOG.exception("Summary job %s failed", job_id)  # the traceback never contains the transcript
            self._jobs.fail(job_id, GENERIC_MESSAGE, self._clock.now())
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

    def _is_still_active(self, job_id: int) -> bool:
        """False when the job was failed meanwhile (e.g. a second app instance recovered it): stop, no LLM call."""
        job = self._jobs.get(job_id)
        if job is None or job.is_finished():
            _LOG.warning("Summary job %s is no longer active: stopping", job_id)
            return False
        return True

    def _progress_writer(self, job_id: int):
        """A callback storing the transcription progress each time it grew by PROGRESS_STEP."""
        last = [0.0]

        def on_progress(fraction: float) -> None:
            if fraction - last[0] >= self.PROGRESS_STEP:
                last[0] = fraction
                self._jobs.set_progress(job_id, fraction, self._clock.now())

        return on_progress


def _generated_line(job: SummaryJob) -> str:
    when = format_local(job.finished_at or job.created_at, "%Y-%m-%d %H:%M")
    return f"Generated on {when}"


def _require_done(job: SummaryJob) -> str:
    if job.status is not JobStatus.DONE or job.summary_text is None:
        raise ValueError("the summary is not ready")
    return job.summary_text


def summary_markdown(job: SummaryJob) -> str:
    """The downloadable `.md`: a title, the generation time and the summary text."""
    return f"# Lecture summary\n\n{_generated_line(job)}\n\n{_require_done(job)}\n"


def summary_plain_text(job: SummaryJob) -> str:
    """The downloadable `.txt`: as the Markdown, without heading signs or bold markers (list dashes stay)."""
    text = re.sub(r"^#{1,6}[ \t]*", "", summary_markdown(job), flags=re.MULTILINE)
    return text.replace("**", "").replace("__", "")
