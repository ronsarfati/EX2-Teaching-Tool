"""T18e minimal tests: F4 pages, API and downloads (FR-4.1, FR-4.6-FR-4.8, FR-6.1). Offline, fakes only."""
import dataclasses
import io

import pytest

from app import create_app
from tests.fakes import (DeferredJobRunner, FakeAudioExtractor, FakeLLMClient, FakeTranscriber,
                         InlineJobRunner)

SUMMARY = "## Topics covered\n**shalom** <script>alert(1)</script> שלום"


def make_client(config, clock, runner=None, cfg=None):
    app = create_app(cfg or config, clock=clock, llm=FakeLLMClient(SUMMARY), transcriber=FakeTranscriber(),
                     audio_extractor=FakeAudioExtractor(), job_runner=runner or InlineJobRunner())
    client = app.test_client()
    return client, app


def login(client):
    client.post("/lecturer/login", data={"pin": "1234"})


def post_video(client, data=b"video", name="lecture.mp4"):
    return client.post("/lecturer/video", data={"video": (io.BytesIO(data), name), "language": "auto"},
                       content_type="multipart/form-data")


def test_everything_requires_the_pin(config, clock):
    client, _ = make_client(config, clock)
    for path in ("/lecturer/video", "/lecturer/video/jobs/1", "/lecturer/video/jobs/1/summary.md"):
        assert client.get(path).status_code == 302
    assert client.get("/api/video/jobs/1").status_code == 401
    assert post_video(client).status_code == 302
    assert client.application.extensions["services"]["video_service"].recent() == []


def test_happy_path_page_escapes_the_summary_and_offers_downloads(config, clock):
    client, _ = make_client(config, clock)
    login(client)
    response = post_video(client)
    assert response.status_code == 303 and response.headers["Location"].endswith("/lecturer/video/jobs/1")
    page = client.get("/lecturer/video/jobs/1").get_data(as_text=True)
    assert "&lt;script&gt;" in page and "<script>alert(1)" not in page
    assert 'dir="auto"' in page and "summary.md" in page and "summary.txt" in page


def test_api_json_keys_and_queued_state(config, clock):
    client, _ = make_client(config, clock, runner=DeferredJobRunner())
    login(client)
    post_video(client)
    body = client.get("/api/video/jobs/1").get_json()
    assert body == {"status": "queued", "label": "Waiting to start", "progress": 0, "finished": False, "error": None}
    assert client.get("/api/video/jobs/99").status_code == 404


def test_downloads_are_utf8_attachments(config, clock):
    client, _ = make_client(config, clock)
    login(client)
    post_video(client)
    md = client.get("/lecturer/video/jobs/1/summary.md")
    txt = client.get("/lecturer/video/jobs/1/summary.txt")
    assert md.headers["Content-Disposition"].startswith('attachment; filename="lecture-summary-')
    assert md.headers["Content-Type"] == "text/markdown; charset=utf-8"
    assert md.get_data(as_text=True).startswith("# Lecture summary") and "שלום" in md.get_data(as_text=True)
    text = txt.get_data(as_text=True)
    assert "#" not in text and "**" not in text and txt.headers["Content-Disposition"].endswith('.txt"')


def test_unfinished_summary_is_404_not_ready(config, clock):
    client, _ = make_client(config, clock, runner=DeferredJobRunner())
    login(client)
    post_video(client)
    response = client.get("/lecturer/video/jobs/1/summary.md")
    assert response.status_code == 404 and "This summary is not ready yet." in response.get_data(as_text=True)


def test_oversize_upload_is_refused_for_this_route_only(config, clock):
    small = dataclasses.replace(config, video_max_bytes=1000)
    client, app = make_client(config, clock, cfg=small)
    login(client)
    response = post_video(client, data=b"x" * 1001)
    assert response.status_code == 413 and "This file is too large. The maximum is" in response.get_data(as_text=True)
    assert app.extensions["services"]["video_service"].recent() == []
    assert post_video(client, data=b"x" * 500).status_code == 303


def test_route_limit_is_above_the_global_25mb(config, clock):
    client, _ = make_client(config, clock)
    login(client)
    assert post_video(client, data=b"x" * (30 * 1024 * 1024)).status_code == 303


def test_bad_extension_and_active_job_listing(config, clock):
    client, _ = make_client(config, clock, runner=DeferredJobRunner())
    login(client)
    assert post_video(client, name="notes.txt").status_code == 400
    post_video(client)
    assert post_video(client).status_code == 409
    page = client.get("/lecturer/video").get_data(as_text=True)
    assert "<form" not in page and "/lecturer/video/jobs/1" in page
