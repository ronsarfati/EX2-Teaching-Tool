"""T22h/T22i: lecturer sub-pages keep their contract strings; busy.js is wired and network-free."""
from pathlib import Path

from tests.fakes import DeferredJobRunner
from tests.test_t18e_video_routes import SUMMARY, login, make_client, post_video

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


def test_busy_js_is_tiny_offline_and_respects_default_prevented():
    source = (STATIC / "busy.js").read_text()
    assert "http" not in source and "defaultPrevented" in source and "data-busy" in source
    assert "aria-busy" in source and len(source.splitlines()) <= 15


def test_busy_forms_load_busy_js_after_video_js(config, clock):
    client, _ = make_client(config, clock)
    login(client)
    video = client.get("/lecturer/video").get_data(as_text=True)
    assert "data-busy" in video and video.index("video.js") < video.index("busy.js")
    for path in ("/lecturer/peers", "/review"):
        assert "busy.js" in client.get(path).get_data(as_text=True), path
    photo = (TEMPLATES / "photo.html").read_text()  # the route needs a session; check the source instead
    assert "data-busy" in photo and "busy.js" in photo


def test_video_job_progress_element_and_cancel_only_while_active(config, clock):
    client, _ = make_client(config, clock, runner=DeferredJobRunner())
    login(client)
    post_video(client)
    page = client.get("/lecturer/video/jobs/1").get_data(as_text=True)
    assert "<progress" in page and "Cancel" in page and "Waiting to start" in page
    assert "video_job.js" in page and "/api/video/jobs/1" in page
    assert "job-1" not in page
    assert "progressEl.value" in (STATIC / "video_job.js").read_text()


def test_done_job_page_has_no_cancel_and_no_polling(config, clock):
    client, _ = make_client(config, clock)
    login(client)
    post_video(client)
    page = client.get("/lecturer/video/jobs/1").get_data(as_text=True)
    assert "Cancel" not in page and "video_job.js" not in page
    assert 'dir="auto"' in page and "summary.md" in page and "summary.txt" in page
    assert "<script>alert(1)" not in page and SUMMARY.split()[0] in page


def test_video_page_form_only_without_active_job(config, clock):
    client, _ = make_client(config, clock, runner=DeferredJobRunner())
    login(client)
    idle = client.get("/lecturer/video").get_data(as_text=True)
    assert "<form" in idle and "No summary yet." in idle
    for value in ('value="auto"', 'value="en"', 'value="he"', 'name="video"'):
        assert value in idle
    post_video(client)
    busy = client.get("/lecturer/video").get_data(as_text=True)
    assert "<form" not in busy and 'name="video"' not in busy
    assert 'jobs/1"' in busy


def test_poll_and_comments_scripts_keep_safe_sinks_and_direction():
    poll = (TEMPLATES / "lecturer_poll.html").read_text()
    comments = (TEMPLATES / "lecturer_comments.html").read_text()
    for source in (poll, comments):
        assert "innerHTML =" not in source and "textContent" in source
        assert "}, 2500)" in source or "refresh, 2500)" in source
    assert "p.dir" in poll and "li.dir" in comments


def test_lecturer_poll_page_strings(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    client.post("/lecturer/polls", data={"question": "<b>Q</b>?", "option": ["a", "b"]})
    page = client.get("/lecturer/polls").get_data(as_text=True)
    assert "Close poll" in page and "&lt;b&gt;Q&lt;/b&gt;" in page and 'dir="auto"' in page
