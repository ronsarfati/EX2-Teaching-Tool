"""D36 (red team 24/11): duration cap, cancel button, LLM retries, export date format. Offline, fakes only."""
import io
import subprocess

import pytest

from app import create_app
from app.adapters.audio import FfmpegAudioExtractor
from app.adapters.transcriber import Transcript
from app.errors import LLMUnavailableError, VideoDurationLimitError
from app.repositories.summaries import JobStatus
from app.services.lecture_summary import LectureSummariser
from app.services.video import VideoSummaryService
from tests.fakes import DeferredJobRunner, FakeAudioExtractor, FakeLLMClient, FakeTranscriber
from tests.test_t18d_video_service import build, upload, work_entries

CANCELLED = "Cancelled by the lecturer."
FOUR_HOURS = VideoSummaryService.VIDEO_MAX_SECONDS


# ---- D36-a: duration cap -------------------------------------------------------------------------
def test_limit_is_four_hours():
    assert FOUR_HOURS == 4 * 3600


@pytest.mark.parametrize("duration", [FOUR_HOURS + 1, 10 * 3600])
def test_over_four_hours_is_refused_and_nothing_is_left(config, clock, duration):
    service, _, extractor, _, llm = build(config, clock, extractor=FakeAudioExtractor(duration=duration))
    with pytest.raises(VideoDurationLimitError) as caught:
        upload(service)
    assert caught.value.user_message == "This recording is longer than 4 hours. Please upload a shorter recording."
    assert caught.value.http_status == 400
    assert service.active() is None and work_entries(config) == []
    assert extractor.calls == [] and llm.calls == []


@pytest.mark.parametrize("duration", [FOUR_HOURS, 60.0, None])
def test_exactly_four_hours_shorter_or_unknown_is_accepted(config, clock, duration):
    service, *_ = build(config, clock, extractor=FakeAudioExtractor(duration=duration))
    assert service.get(upload(service).id).status is JobStatus.DONE


def test_ffprobe_command_is_a_list_without_shell(monkeypatch, tmp_path):
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return subprocess.CompletedProcess(command, 0, b"5400.25\n", b"")

    monkeypatch.setattr(subprocess, "run", run)
    assert FfmpegAudioExtractor().duration_seconds(tmp_path / "input.mp4") == 5400.25
    assert seen["command"] == ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                               "-of", "default=noprint_wrappers=1:nokey=1", str(tmp_path / "input.mp4")]
    assert not seen["kwargs"].get("shell") and seen["kwargs"]["timeout"] <= 60


@pytest.mark.parametrize("outcome", [b"N/A\n", b"", b"nan\n", b"-3\n", b"inf\n"])
def test_ffprobe_unusable_output_gives_none(monkeypatch, tmp_path, outcome):
    monkeypatch.setattr(subprocess, "run", lambda c, **k: subprocess.CompletedProcess(c, 0, outcome, b""))
    assert FfmpegAudioExtractor().duration_seconds(tmp_path / "i.mp4") is None


def test_ffprobe_failure_missing_or_timeout_gives_none(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda c, **k: subprocess.CompletedProcess(c, 1, b"12\n", b"bad"))
    assert FfmpegAudioExtractor().duration_seconds(tmp_path / "i.mp4") is None

    def missing(command, **kwargs):
        raise FileNotFoundError

    def hang(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 30)

    for failure in (missing, hang):
        monkeypatch.setattr(subprocess, "run", failure)
        assert FfmpegAudioExtractor().duration_seconds(tmp_path / "i.mp4") is None


def test_upload_route_answers_400_for_a_too_long_recording(config, clock):
    app = create_app(config, clock=clock, llm=FakeLLMClient("x"), transcriber=FakeTranscriber(),
                     audio_extractor=FakeAudioExtractor(duration=FOUR_HOURS + 1), job_runner=DeferredJobRunner())
    client = app.test_client()
    client.post("/lecturer/login", data={"pin": "1234"})
    response = client.post("/lecturer/video", data={"video": (io.BytesIO(b"v"), "a.mp4"), "language": "auto"},
                           content_type="multipart/form-data")
    assert response.status_code == 400 and "longer than 4 hours" in response.get_data(as_text=True)
    assert app.extensions["services"]["video_service"].active() is None


# ---- D36-a: cancel ---------------------------------------------------------------------------------
def make_client(config, clock, **kwargs):
    runner = kwargs.pop("runner", DeferredJobRunner())
    app = create_app(config, clock=clock, llm=FakeLLMClient("x"), transcriber=FakeTranscriber(),
                     audio_extractor=FakeAudioExtractor(), job_runner=runner)
    client = app.test_client()
    client.post("/lecturer/login", data={"pin": "1234"})
    return client, app.extensions["services"]["video_service"]


def test_cancel_route_needs_the_pin(config, clock):
    client, service = make_client(config, clock)
    upload(service)
    anonymous = client.application.test_client()
    assert anonymous.post("/lecturer/video/jobs/1/cancel").status_code == 302
    assert service.get(1).status is JobStatus.QUEUED


def test_cancel_route_unknown_id_is_404(config, clock):
    client, _ = make_client(config, clock)
    assert client.post("/lecturer/video/jobs/999/cancel").status_code == 404


def test_cancel_route_fails_the_job_and_frees_the_slot(config, clock):
    client, service = make_client(config, clock)
    upload(service)
    response = client.post("/lecturer/video/jobs/1/cancel")
    assert response.status_code == 303 and response.headers["Location"].endswith("/lecturer/video/jobs/1")
    job = service.get(1)
    assert job.status is JobStatus.FAILED and job.error_message == CANCELLED
    assert service.active() is None
    assert CANCELLED in client.get("/lecturer/video/jobs/1").get_data(as_text=True)
    upload(service)  # the slot is free: a new recording is accepted


def test_cancel_route_leaves_a_finished_job_unchanged(config, clock):
    service, app, *_ = build(config, clock)  # inline runner: the job is done at once
    job = upload(service)
    client = app.test_client()
    client.post("/lecturer/login", data={"pin": "1234"})
    assert client.post(f"/lecturer/video/jobs/{job.id}/cancel").status_code == 303
    after = service.get(job.id)
    assert after.status is JobStatus.DONE and after.error_message is None


def test_cancel_button_only_while_the_job_is_active(config, clock):
    client, service = make_client(config, clock)
    upload(service)
    assert "/lecturer/video/jobs/1/cancel" in client.get("/lecturer/video/jobs/1").get_data(as_text=True)
    client.post("/lecturer/video/jobs/1/cancel")
    assert "/cancel" not in client.get("/lecturer/video/jobs/1").get_data(as_text=True)


def test_cancel_during_transcription_stops_without_an_llm_call(config, clock):
    box = []
    transcriber = FakeTranscriber(on_call=lambda: box[0].cancel(box[0].active().id))
    service, _, _, _, llm = build(config, clock, transcriber=transcriber)
    box.append(service)
    job = upload(service)
    assert service.get(job.id).error_message == CANCELLED and service.get(job.id).status is JobStatus.FAILED
    assert llm.calls == [] and work_entries(config) == []


def test_cancel_between_map_parts_stops_the_remaining_calls(config, clock):
    box = []

    def reply(prompt):
        box[0].cancel(box[0].active().id)  # the lecturer clicks while the first part is being summarised
        return "notes"

    llm = FakeLLMClient(reply)
    transcript = Transcript("word " * 20_000, "en", 100.0)  # above one chunk: map-reduce
    service, *_ = build(config, clock, llm=llm, transcriber=FakeTranscriber(transcript))
    box.append(service)
    job = upload(service)
    assert len(llm.calls) == 1
    assert service.get(job.id).status is JobStatus.FAILED and service.get(job.id).error_message == CANCELLED
    assert work_entries(config) == []


# ---- D36-b: retries ----------------------------------------------------------------------------------
class FlakyLLM(FakeLLMClient):
    """Raises LLMUnavailableError `failures` times, then answers `reply`."""

    def __init__(self, failures, reply="ok"):
        super().__init__(reply)
        self.failures = failures

    def complete(self, system, prompt, max_tokens, feature="review"):
        if len(self.calls) < self.failures:
            self.calls.append({})
            raise LLMUnavailableError(feature)
        return super().complete(system, prompt, max_tokens, feature)


def summarise(llm, sleeps, is_cancelled=lambda: False):
    return LectureSummariser(llm, sleep=sleeps.append).summarise(Transcript("hello", "en", 1.0), None, is_cancelled)


def test_succeeds_on_the_third_attempt_after_waiting_2_then_8_seconds():
    llm, sleeps = FlakyLLM(2), []
    assert summarise(llm, sleeps) == "ok"
    assert len(llm.calls) == 3 and sleeps == [2, 8]


def test_fails_after_three_attempts():
    llm, sleeps = FlakyLLM(99), []
    with pytest.raises(LLMUnavailableError):
        summarise(llm, sleeps)
    assert len(llm.calls) == 3 and sleeps == [2, 8]


def test_no_retry_on_an_empty_answer():
    llm, sleeps = FakeLLMClient("  "), []
    with pytest.raises(LLMUnavailableError):
        summarise(llm, sleeps)
    assert len(llm.calls) == 1 and sleeps == []


def test_no_retry_without_a_key():
    llm, sleeps = FakeLLMClient(error=LLMUnavailableError("summary"), configured=False), []
    with pytest.raises(LLMUnavailableError):
        summarise(llm, sleeps)
    assert len(llm.calls) == 1 and sleeps == []


def test_no_retry_after_a_cancel():
    from app.errors import JobCancelledError
    llm, sleeps, state = FlakyLLM(99), [], {"cancelled": False}
    summariser = LectureSummariser(llm, sleep=lambda s: state.update(cancelled=True))  # cancelled while waiting
    with pytest.raises(JobCancelledError):
        summariser.summarise(Transcript("hello", "en", 1.0), None, lambda: state["cancelled"])
    assert len(llm.calls) == 1


def test_each_map_part_and_the_reduce_retry_on_their_own():
    class FailFirstOfEach(FakeLLMClient):
        def __init__(self):
            super().__init__("n")
            self.attempts = {}

        def complete(self, system, prompt, max_tokens, feature="review"):
            key = prompt[:80] + str(max_tokens)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            if self.attempts[key] == 1:
                raise LLMUnavailableError(feature)
            return super().complete(system, prompt, max_tokens, feature)

    llm, sleeps = FailFirstOfEach(), []
    LectureSummariser(llm, max_chunk_chars=100, sleep=sleeps.append).summarise(
        Transcript("word " * 60, "en", 1.0), None)
    assert len(llm.calls) == 3 + 1 and len(sleeps) == 4 and set(sleeps) == {2}


# ---- D36-c: export date and time ---------------------------------------------------------------------
def test_checked_in_cell_shows_date_and_time_after_midnight(app, client, clock):
    from tests.test_export import run_session
    from tests.test_timezone import utc
    client.post("/lecturer/login", data={"pin": "1234"})
    clock.set(utc(2026, 11, 23, 22, 30))  # 00:30 the next day in Jerusalem
    run_session(app, app.extensions["services"], ["Fox"])
    text = client.get("/lecturer/export/checkins.csv").get_data(as_text=True)
    assert text.splitlines()[1].endswith(",2026-11-24 00:30:00")


def test_dst_fold_repeats_the_wall_clock_time_known_limit():
    from app.timezone import format_local
    from tests.test_timezone import utc
    # 24/10/2026 22:30 UTC is 01:30 summer time, 23:30 UTC is 01:30 winter time: the wall clock repeats (known limit; the stored UTC values stay distinct).
    assert format_local(utc(2026, 10, 24, 22, 30), "%Y-%m-%d %H:%M:%S") == "2026-10-25 01:30:00"
    assert format_local(utc(2026, 10, 24, 23, 30), "%Y-%m-%d %H:%M:%S") == "2026-10-25 01:30:00"
