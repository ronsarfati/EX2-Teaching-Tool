"""T18d minimal tests: job service with fakes (FR-4.2-FR-4.9). No ffmpeg, model, key or network."""
import io
import logging

import pytest

from app import create_app
from app.adapters.transcriber import Transcript
from app.errors import (LLMUnavailableError, SummaryJobRunningError, TranscriptionUnavailableError,
                        UnreadableVideoError, UnsupportedVideoFormatError)
from app.repositories.summaries import JobStatus
from tests.fakes import (DeferredJobRunner, FakeAudioExtractor, FakeLLMClient, FakeTranscriber,
                         InlineJobRunner)

MARKER = "zebrafishmarker"


def build(config, clock, *, runner=None, extractor=None, transcriber=None, llm=None):
    runner = runner or InlineJobRunner()
    extractor = extractor or FakeAudioExtractor()
    transcriber = transcriber or FakeTranscriber(Transcript(f"hello {MARKER}", "en", 30.0))
    llm = llm or FakeLLMClient("## Topics covered\nclasses")
    app = create_app(config, clock=clock, llm=llm, transcriber=transcriber, audio_extractor=extractor,
                     job_runner=runner)
    return app.extensions["services"]["video_service"], app, extractor, transcriber, llm


def work_entries(config):
    from pathlib import Path
    root = Path(config.video_work_dir)
    return [p.name for p in root.iterdir()] if root.exists() else []


def upload(service, name="lecture.MP4", language="auto", data=b"video-bytes"):
    return service.submit(io.BytesIO(data), name, language)


def test_success_stores_summary_and_deletes_files(config, clock):
    service, _, extractor, transcriber, llm = build(config, clock)
    job = service.get(upload(service, language="he").id)
    assert job.status is JobStatus.DONE and job.summary_text.startswith("## Topics")
    assert (job.detected_language, job.media_seconds, job.progress) == ("en", 30.0, 1.0)
    assert work_entries(config) == []
    assert extractor.input_existed == [True] and transcriber.audio_existed == [True]
    assert "`he`" in llm.calls[0]["prompt"]


def test_bad_extension_creates_nothing(config, clock):
    service, *_ = build(config, clock)
    for name in ("notes.txt", "noextension", ""):
        with pytest.raises(UnsupportedVideoFormatError):
            upload(service, name)
    assert service.recent() == [] and work_entries(config) == []


def test_no_key_refuses_before_any_job(config, clock):
    service, *_ = build(config, clock, llm=FakeLLMClient(configured=False))
    with pytest.raises(LLMUnavailableError):
        upload(service)
    assert service.recent() == [] and work_entries(config) == []


def test_second_upload_refused_while_one_is_queued(config, clock):
    runner = DeferredJobRunner()
    service, *_ = build(config, clock, runner=runner)
    first = upload(service)
    assert service.get(first.id).status is JobStatus.QUEUED
    with pytest.raises(SummaryJobRunningError):
        upload(service)
    assert work_entries(config) == [f"job-{first.id}"]
    runner.run_all()
    assert service.get(first.id).status is JobStatus.DONE and work_entries(config) == []
    upload(service)  # the slot is free again


def test_empty_upload_is_refused_and_cleaned(config, clock):
    service, *_ = build(config, clock)
    with pytest.raises(UnreadableVideoError):
        upload(service, data=b"")
    job = service.recent()[0]
    assert job.status is JobStatus.FAILED and job.error_message == "We could not read this video file."
    assert work_entries(config) == []


@pytest.mark.parametrize("kwargs, message", [
    ({"extractor": FakeAudioExtractor(error=UnreadableVideoError())}, "We could not read this video file."),
    ({"extractor": FakeAudioExtractor(error=TranscriptionUnavailableError())},
     "The transcription service is unavailable right now. Please try again later."),
    ({"transcriber": FakeTranscriber(error=TranscriptionUnavailableError())},
     "The transcription service is unavailable right now. Please try again later."),
    ({"transcriber": FakeTranscriber(Transcript("  \n", "en", 5.0))}, "No speech was found in this recording."),
    ({"llm": FakeLLMClient(error=LLMUnavailableError("summary"))},
     "The summary service is unavailable right now. Please try again later."),
    ({"transcriber": FakeTranscriber(error=RuntimeError("secret /path"))}, "Something went wrong. Please try again."),
])
def test_every_failure_path_fails_the_job_and_cleans_up(config, clock, kwargs, message):
    service, *_ = build(config, clock, **kwargs)
    job = service.get(upload(service).id)
    assert (job.status, job.error_message, job.summary_text) == (JobStatus.FAILED, message, None)
    assert work_entries(config) == []


def test_runner_error_fails_the_job_and_cleans_up(config, clock):
    class BrokenRunner:
        def submit(self, task):
            raise RuntimeError("no threads")

    service, *_ = build(config, clock, runner=BrokenRunner())
    with pytest.raises(RuntimeError):
        upload(service)
    assert service.recent()[0].status is JobStatus.FAILED and work_entries(config) == []


def test_transcript_is_never_stored_or_logged(config, clock, caplog):
    caplog.set_level(logging.DEBUG)
    service, *_ = build(config, clock, llm=FakeLLMClient(error=LLMUnavailableError("summary")))
    upload(service)
    dump = "\n".join(str(tuple(row)) for table in ("summary_job",)
                     for row in service._jobs._db.conn().execute(f"SELECT * FROM {table}"))
    assert MARKER not in dump and MARKER not in caplog.text and work_entries(config) == []


def test_statuses_are_observed_in_order(config, clock):
    seen = []
    holder = {}
    transcriber = FakeTranscriber(on_call=lambda: seen.append(holder["service"].active().status))
    service, *_ = build(config, clock, transcriber=transcriber,
                        llm=FakeLLMClient(lambda prompt: seen.append(holder["service"].active().status) or "ok"))
    holder["service"] = service
    upload(service)
    assert seen == [JobStatus.TRANSCRIBING, JobStatus.SUMMARISING]


def test_recovery_marks_active_jobs_failed_and_removes_job_dirs(config, clock):
    service, *_ = build(config, clock, runner=DeferredJobRunner())
    job = upload(service)
    keep = service._work_root / "keep.txt"
    keep.write_text("x")
    app = create_app(config, clock=clock)  # a restart
    restarted = app.extensions["services"]["video_service"]
    failed = restarted.get(job.id)
    assert failed.status is JobStatus.FAILED and "interrupted" in failed.error_message
    assert keep.exists() and not (service._work_root / f"job-{job.id}").exists()


def test_unknown_language_means_same_as_lecture(config, clock):
    service, *_ = build(config, clock)
    assert service.get(upload(service, language="xx").id).summary_language is None
    assert service.get(upload(service, language="en").id).summary_language == "en"
