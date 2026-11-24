"""T18a minimal tests: F4 config, error messages, job state machine, repository (FR-4.5, FR-4.6)."""
import sqlite3

import pytest

from app.config import Config, ConfigError
from app.db import Database
from app.errors import SummaryJobRunningError, VideoTooLargeError
from app.repositories.summaries import JobStatus, SummaryRepository

ENV = {"LECTURER_PIN": "1234", "SECRET_KEY": "s", "BASE_URL": "https://test.example"}


@pytest.fixture
def repo(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.init_schema()
    return SummaryRepository(db)


def test_config_defaults():
    config = Config.from_env(ENV)
    assert (config.whisper_model, config.whisper_language, config.video_max_bytes) == ("small", None, 2147483648)


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_bad_video_max_bytes_is_refused(value):
    with pytest.raises(ConfigError):
        Config.from_env({**ENV, "VIDEO_MAX_BYTES": value})


def test_too_large_message_quotes_the_limit():
    assert VideoTooLargeError(2147483648).user_message == "This file is too large. The maximum is 2 GB."
    assert VideoTooLargeError(1048576).user_message == "This file is too large. The maximum is 1 MB."
    assert VideoTooLargeError(104857600).user_message == "This file is too large. The maximum is 100 MB."
    assert VideoTooLargeError(1610612736).user_message == "This file is too large. The maximum is 1.5 GB."


def test_status_transitions_are_forward_only():
    order = [JobStatus.QUEUED, JobStatus.EXTRACTING, JobStatus.TRANSCRIBING, JobStatus.SUMMARISING, JobStatus.DONE]
    for a in JobStatus:
        for b in JobStatus:
            if a in order[:-1]:
                expected = b is JobStatus.FAILED or order.index(b) == order.index(a) + 1 if b in order else b is JobStatus.FAILED
            else:
                expected = False
            assert a.can_move_to(b) == expected, (a, b)


def test_create_move_finish_and_single_active_job(repo):
    job = repo.create("he", 1.0)
    assert job.status is JobStatus.QUEUED and repo.active().id == job.id
    with pytest.raises(SummaryJobRunningError):
        repo.create(None, 2.0)
    with pytest.raises(ValueError):
        repo.move(job.id, JobStatus.SUMMARISING, 2.0)  # skips two steps
    for status in (JobStatus.EXTRACTING, JobStatus.TRANSCRIBING, JobStatus.SUMMARISING):
        repo.move(job.id, status, 2.0)
    repo.finish(job.id, "text", "he", 12.5, 3.0)
    done = repo.get(job.id)
    assert (done.status, done.summary_text, done.progress, done.finished_at) == (JobStatus.DONE, "text", 1.0, 3.0)
    repo.fail(job.id, "late", 4.0)
    assert repo.get(job.id).status is JobStatus.DONE  # a done job never becomes failed
    assert repo.create(None, 5.0).id != job.id


def test_database_refuses_a_second_active_row_and_stray_text(repo):
    repo.create(None, 1.0)
    conn = repo._db.conn()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO summary_job(status, created_at, updated_at) VALUES ('queued', 1, 1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE summary_job SET summary_text = 'x' WHERE is_active = 1")


def test_no_transcript_or_file_column(repo):
    columns = [row["name"] for row in repo._db.conn().execute("PRAGMA table_info(summary_job)")]
    assert not [c for c in columns if any(w in c for w in ("transcript", "file", "name", "path"))]
