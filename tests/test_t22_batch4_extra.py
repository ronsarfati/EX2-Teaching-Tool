"""T22h/T22i extra: rendered photo result, video job pages, review page, and busy.js / video_job.js run with node."""
import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app import create_app
from app.adapters.repo_fetcher import RepoExtract
from app.errors import UnreadableVideoError
from tests.fakes import (DeferredJobRunner, FakeAudioExtractor, FakeHeadCounter, FakeLLMClient,
                         FakeRepoFetcher, FakeTranscriber, InlineJobRunner)
from tests.test_t18e_video_routes import login, make_client, post_video

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
TEMPLATES = ROOT / "app" / "templates"
NODE = shutil.which("node") or "/usr/local/bin/node"
needs_node = pytest.mark.skipif(not Path(NODE).exists(), reason="node not installed")


def test_photo_result_page_exact_counts(config, clock):
    """Covers T22h: the real POST result contains `<strong>N</strong> / detected <strong>D</strong>`."""
    app = create_app(config, clock=clock, head_counter=FakeHeadCounter(count=7))
    client = app.test_client()
    login(client)
    client.post("/lecturer/sessions")
    page = client.post("/lecturer/sessions/1/photo", data={"photo": (io.BytesIO(b"img"), "p.jpg")},
                       content_type="multipart/form-data").get_data(as_text=True)
    assert "<strong>0</strong> / detected <strong>7</strong>" in page
    assert "data-busy" in page and "busy.js" in page


def _links(page):
    return [int(m) for m in re.findall(r'href="[^"]*jobs/(\d+)"', page)]


def test_video_page_active_job_no_form_and_newest_first(config, clock):
    """Covers T22h: with an active job there is no form/upload field; recent links newest first."""
    runner = DeferredJobRunner()
    client, _ = make_client(config, clock, runner=runner)
    login(client)
    post_video(client)
    runner.run_all()  # job 1 done
    post_video(client)  # job 2 queued (active)
    page = client.get("/lecturer/video").get_data(as_text=True)
    assert "<form" not in page and 'name="video"' not in page
    ids = _links(page)
    assert 'jobs/2"' in page and 'jobs/1"' in page
    assert ids.index(2) < ids.index(1) and ids == sorted(ids, reverse=True)


def test_active_job_page_elements_and_no_id_with_job_number(config, clock):
    """Covers T22h: queued page has progress, Cancel, waiting text, api path, video_job.js; no id embeds the job id."""
    runner = DeferredJobRunner()
    client, _ = make_client(config, clock, runner=runner)
    login(client)
    for _ in range(2):  # job 1 finished, job 2 queued
        post_video(client)
        runner.run_all() if _ == 0 else None
    page = client.get("/lecturer/video/jobs/2").get_data(as_text=True)
    for needle in ('<progress id="job-progress"', "Cancel", "Waiting to start", "/api/video/jobs/2", "video_job.js"):
        assert needle in page, needle
    assert not [i for i in re.findall(r'\bid="([^"]*)"', page) if "2" in i or "job-2" in i]


def test_done_and_failed_pages_have_no_cancel_nor_polling(config, clock):
    """Covers T22h: ended jobs show neither Cancel nor video_job.js."""
    client, _ = make_client(config, clock)
    login(client)
    post_video(client)
    app = create_app(config, clock=clock, llm=FakeLLMClient("x"), job_runner=InlineJobRunner(),
                     transcriber=FakeTranscriber(),
                     audio_extractor=FakeAudioExtractor(error=UnreadableVideoError()))
    failing = app.test_client()
    login(failing)
    post_video(failing)
    for c, jid in ((client, 1), (failing, 2)):  # same database: the failing app's job is number 2
        page = c.get(f"/lecturer/video/jobs/{jid}").get_data(as_text=True)
        assert "Cancel" not in page and "video_job.js" not in page and "<progress" not in page
    assert "could not read this video" in failing.get("/lecturer/video/jobs/2").get_data(as_text=True)


def test_poll_and_comments_scripts_contract():
    """Covers T22h: 2500 ms, textContent, dir, no innerHTML assignment."""
    for name, marker in (("lecturer_poll.html", "p.dir"), ("lecturer_comments.html", "li.dir")):
        src = (TEMPLATES / name).read_text()
        assert "2500" in src and "textContent" in src and marker in src
        assert "innerHTML =" not in src and "innerHTML=" not in src
    assert 'dir="auto"' in (TEMPLATES / "lecturer_comments.html").read_text() or "dir" in (TEMPLATES / "lecturer_comments.html").read_text()


def test_review_page_counts_and_submission_label(config, clock):
    """Covers T22h: 'N files, M lines' and 'Submission B:' in the rendered review result."""
    target, peer = "https://github.com/a-example/t", "https://github.com/b-example/p"
    fetcher = FakeRepoFetcher({target: RepoExtract("x", 3, 42, False), peer: RepoExtract("y", 7, 111, False)})
    app = create_app(config, clock=clock, llm=FakeLLMClient("Fine."), fetcher=fetcher)
    client = app.test_client()
    login(client)
    app.extensions["services"]["reviewer"].set_peer_repos([peer])
    page = client.post("/review", data={"url": target}).get_data(as_text=True)
    assert "3 files, 42 lines" in page and "Submission B: 7 files, 111 lines" in page


def test_every_data_busy_template_includes_busy_js():
    """Covers T22i: each template with a data-busy form loads busy.js."""
    found = [p for p in TEMPLATES.glob("*.html") if "data-busy" in p.read_text()]
    assert {p.name for p in found} >= {"photo.html", "review.html", "video.html", "peers.html"}
    for p in found:
        assert "busy.js" in p.read_text(), p.name


def _node(script: str) -> str:
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


BUSY_HARNESS = r"""
const fs = require('fs');
let handlers = {};
const mkForm = (busy) => { const btn = {attrs:{}, disabled:false, setAttribute(k,v){this.attrs[k]=v;},
    removeAttribute(k){ delete this.attrs[k]; }};
  return {btn, hasAttribute: (n) => busy && n === 'data-busy', querySelector: () => btn}; };
let buttons = [];
global.document = {addEventListener(t, f){ handlers[t] = f; }, querySelectorAll: () => buttons};
global.window = {addEventListener(t, f){ handlers[t] = f; }};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const a = mkForm(true); handlers.submit({target: a, defaultPrevented: false});
const b = mkForm(true); handlers.submit({target: b, defaultPrevented: true});
const c = mkForm(false); handlers.submit({target: c, defaultPrevented: false});
console.log(JSON.stringify([a.btn, b.btn, c.btn, Object.keys(handlers)]));
"""


@needs_node
def test_busy_js_behaviour_in_node():
    """Covers T22i: submit sets aria-busy+disabled; defaultPrevented or non-busy form untouched."""
    out = subprocess.run([NODE, "-e", BUSY_HARNESS, str(STATIC / "busy.js")], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    a, b, c, events = json.loads(out.stdout)
    assert a["disabled"] is True and a["attrs"] == {"aria-busy": "true"}
    assert b["disabled"] is False and b["attrs"] == {}
    assert c["disabled"] is False and c["attrs"] == {}
    assert sorted(events) == ["pageshow", "submit"]


@needs_node
def test_busy_js_bfcache_pageshow_reenables_buttons_only_when_persisted():
    """Covers T22i: after a bfcache restore (persisted=true) the button is enabled again and not aria-busy;
    a normal pageshow (persisted=false) changes nothing."""
    harness = BUSY_HARNESS.split("const a = mkForm")[0] + r"""
const run = (persisted) => { const f = mkForm(true); buttons = [f.btn]; handlers.submit({target: f, defaultPrevented: false});
  handlers.pageshow({persisted}); return f.btn; };
console.log(JSON.stringify([run(true), run(false)]));
"""
    out = subprocess.run([NODE, "-e", harness, str(STATIC / "busy.js")], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    restored, untouched = json.loads(out.stdout)
    assert restored["disabled"] is False and restored["attrs"] == {}
    assert untouched["disabled"] is True and untouched["attrs"] == {"aria-busy": "true"}


JOB_HARNESS = r"""
const fs = require('fs');
const run = async (data) => {
  const els = {"job-label": {textContent: ""}, "job-progress": {value: undefined, max: undefined, attrs: {value: 1},
      removeAttribute(n){ delete this.attrs[n]; this.value = undefined; }}, "job-error": {hidden: true}};
  let tick;
  global.document = {getElementById: (i) => els[i], body: {dataset: {api: "/api/video/jobs/9"}}};
  global.location = {reload(){ els.reloaded = true; }};
  global.fetch = async () => ({ok: true, json: async () => data});
  global.setInterval = (f) => { tick = f; };
  eval(fs.readFileSync(process.argv[1], 'utf8'));
  await tick();
  const v = els["job-progress"].value; return {value: v === undefined ? null : v, max: els["job-progress"].max, hasAttr: "value" in els["job-progress"].attrs,
          label: els["job-label"].textContent, reloaded: !!els.reloaded};
};
(async () => {
  const out = [];
  out.push(await run({status: "transcribing", progress: 40, label: "Transcribing", finished: false}));
  out.push(await run({status: "queued", progress: 0, label: "Waiting to start", finished: false}));
  out.push(await run({status: "summarising", progress: 100, label: "Summarising", finished: false}));
  out.push(await run({status: "done", finished: true}));
  console.log(JSON.stringify(out));
})();
"""


@needs_node
def test_video_job_js_progress_value_only_while_transcribing():
    """Covers T22h: <progress> gets value while transcribing; indeterminate otherwise; reload when finished."""
    out = subprocess.run([NODE, "-e", JOB_HARNESS, str(STATIC / "video_job.js")], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    transcribing, queued, summarising, done = json.loads(out.stdout)
    assert transcribing["value"] == 40 and transcribing["max"] == 100 and transcribing["label"] == "Transcribing"
    for state in (queued, summarising):
        assert state["value"] is None and state["hasAttr"] is False
    assert queued["label"] == "Waiting to start" and done["reloaded"] is True
