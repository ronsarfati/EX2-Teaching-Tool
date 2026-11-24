"""T22c/T22d extra acceptance (D38): dashboard states, link resolution, JS invariants, JS behaviour via node."""
import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


@pytest.fixture
def lec(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def _html(c, path="/lecturer"):
    return c.get(path).get_data(as_text=True)


def _hrefs(html):
    return re.findall(r'href="([^"#][^"]*)"', html)


def test_closed_dashboard_primary_action(lec):
    """Covers T22c: closed chip data-state, Open session form, no Projector link, no close/confirm."""
    html = _html(lec)
    assert 'data-state="closed"' in html and 'data-state="live"' not in html
    assert re.search(r'<form[^>]*action="/lecturer/sessions"[^>]*>\s*<button[^>]*>Open session', html)
    assert "Close session" not in html and "confirm(" not in html
    assert "Projector" not in html.split("</nav>")[1]
    for ident in ('id="n"', 'id="d"', 'id="status"', 'id="attendance-rows"', 'id="attendance-error"'):
        assert ident not in html


def test_open_dashboard_primary_action(lec):
    """Covers T22c: live chip, close form with confirm, projector link, no Open session, ids present."""
    lec.post("/lecturer/sessions")
    html = _html(lec)
    body = html.split("</nav>")[1]
    assert 'data-state="live"' in html and 'data-state="closed"' not in html
    assert "Open session" not in html
    assert "confirm('Close the session?" in html
    assert body.count('href="/lecturer/projector"') == 1
    for ident in ("n", "d", "status", "attendance-rows", "attendance-error"):
        assert len(re.findall(f'id="{ident}"', html)) == 1
    assert "/static/poll_json.js" in html and "dataset.api" in html


def test_close_then_reopen_cycle(lec):
    """Covers T22c: the confirm-protected close form really closes; dashboard returns to closed state."""
    lec.post("/lecturer/sessions")
    action = re.search(r'<form method="post" action="([^"]+)"\s+onsubmit', _html(lec)).group(1)
    assert lec.post(action).status_code in (200, 302)
    assert 'data-state="closed"' in _html(lec)


@pytest.mark.parametrize("opened", [False, True])
def test_all_dashboard_links_resolve(lec, opened):
    """Covers T22c: every internal link on the dashboard answers (no 404/500), exports have right type."""
    if opened:
        lec.post("/lecturer/sessions")
    html = _html(lec)
    links = [h for h in _hrefs(html) if h.startswith("/") and not h.startswith("/static")]
    expected = {"/lecturer/export.xlsx", "/lecturer/export/checkins.csv", "/lecturer/export/summary.csv",
                "/lecturer/polls", "/lecturer/comments", "/lecturer/video", "/review", "/lecturer/peers"}
    assert expected <= set(links)
    for href in links:
        r = lec.get(href)
        assert r.status_code == 200, (href, r.status_code)
    assert "spreadsheetml" in lec.get("/lecturer/export.xlsx").content_type
    assert "csv" in lec.get("/lecturer/export/checkins.csv").content_type
    assert "csv" in lec.get("/lecturer/export/summary.csv").content_type


def test_open_dashboard_photo_and_projector_links_resolve(lec):
    """Covers T22c: photo link (session id) and projector link resolve when open."""
    lec.post("/lecturer/sessions")
    html = _html(lec)
    photo = [h for h in _hrefs(html) if "photo" in h]
    assert photo and all(lec.get(h).status_code == 200 for h in photo)
    assert lec.get("/lecturer/projector").status_code == 200


def test_static_assets_served(lec):
    """Covers T22c/T22d: the JS and CSS referenced exist and are served."""
    for name in ("poll_json.js", "projector.js", "app.css"):
        assert lec.get(f"/static/{name}").status_code == 200


def test_poll_json_invariants():
    """Covers T22c: POLL_MS, interval, textContent, no innerHTML, dir auto, dataset.state."""
    js = (STATIC / "poll_json.js").read_text()
    code = re.sub(r"//.*", "", js)
    assert "const POLL_MS = 2500;" in js and "setInterval(poll, POLL_MS)" in js
    for t in ("nEl.textContent", "dEl.textContent", "statusEl.textContent", "td.textContent"):
        assert t in js
    assert "innerHTML" not in code and "td.dir = \"auto\"" in js and "dataset.state" in js


def test_projector_page_invariants(lec):
    """Covers T22d: forced light theme, ids, no external reference, no nav, error element separate."""
    lec.post("/lecturer/sessions")
    html = _html(lec, "/lecturer/projector")
    assert '<html lang="en" data-theme="light">' in html
    for ident in ("qr", "code", "waiting", "projector-error"):
        assert len(re.findall(f'id="{ident}"', html)) == 1
    assert "http" not in html and "cdn" not in html.lower() and "<nav" not in html
    assert not re.search(r'(src|href)="//', html)
    assert re.search(r'id="waiting"[^>]*>No session is open\.</p>', html)
    assert not re.search(r'id="waiting"[^>]*>[^<]*Connection', html)
    assert re.search(r'id="projector-error"[^>]*>Connection problem', html)
    assert "/static/projector.js" in html


def test_projector_js_invariants():
    """Covers T22d: POLL_MS, no absolute URL, errors target #projector-error only."""
    js = (STATIC / "projector.js").read_text()
    assert "const POLL_MS = 1000;" in js and "setInterval(poll, POLL_MS)" in js
    assert not re.search(r"https?://|//cdn", re.sub(r"//.*", "", js))
    assert "innerHTML" not in js
    assert "waitingEl.textContent" not in js


def test_projector_api_keys_unchanged(lec):
    """Covers T22d: JSON keys the projector polls (closed: open; open: open, qr, code)."""
    closed = lec.get("/api/projector").get_json()
    assert closed["open"] is False
    lec.post("/lecturer/sessions")
    data = lec.get("/api/projector").get_json()
    assert {"open", "qr", "code"} <= set(data)
    assert data["qr"].startswith("data:image/png;base64,") and re.fullmatch(r"\d{4}", str(data["code"]))


def test_attendance_api_keys_unchanged(lec):
    """Covers T22c: keys poll_json.js reads: n, head_count, consistency, check_ins[nickname, checked_in_at]."""
    lec.post("/lecturer/sessions")
    api = re.search(r'dataset\.api = "([^"]+)"', _html(lec)).group(1)
    data = lec.get(api).get_json()
    assert {"n", "head_count", "consistency", "check_ins"} <= set(data)
    assert data["check_ins"] == [] and data["head_count"] is None and data["consistency"] is None


# --- JS behaviour with a tiny DOM stub (needs node) -------------------------------------------------------

NODE = shutil.which("node")
HARNESS = textwrap.dedent("""
    const vm = require("vm"), fs = require("fs");
    function el(id) { return {id, hidden: false, textContent: "", src: "", dataset: {}, children: [],
      listeners: {}, addEventListener(e, f) { this.listeners[e] = f; },
      replaceChildren(...c) { this.children = c; }, append(...c) { this.children.push(...c); }}; }
    const ids = {};
    for (const i of ["qr","code","waiting","waiting-hint","qr-box","steps","projector-error","fullscreen",
                     "attendance-rows","n","d","status","attendance-error"]) ids[i] = el(i);
    const timers = [];
    let responses = [];
    const ctx = {
      document: { body: {dataset: {api: "/x"}}, getElementById: (i) => ids[i],
                  createElement: (t) => ({tag: t, children: [], textContent: "", append(...c) { this.children.push(...c); }}),
                  documentElement: {requestFullscreen() {}} },
      fetch: async () => { const r = responses.shift(); if (r instanceof Error) throw r; return r; },
      setInterval: (f, ms) => timers.push([f, ms]), Date, console };
    vm.createContext(ctx);
    const run = (file) => vm.runInContext(fs.readFileSync(file, "utf8") + "\\n;globalThis.__poll = poll;", ctx);
    const ok = (body) => ({ok: true, json: async () => body});
    const out = {};
    (async () => {
      const mode = process.argv[2];
      if (mode === "projector") {
        responses = [new Error("net"), ok({open: false}), ok({open: true, qr: "data:q", code: "1234"}), ok({open: false})];
        run(process.argv[3]);
        await new Promise((r) => setTimeout(r, 10));            // initial poll: failure
        out.afterError = {err: ids["projector-error"].hidden, waiting: ids.waiting.textContent, waitingHidden: ids.waiting.hidden};
        await ctx.__poll();                                      // success, no session
        out.afterSuccess = {err: ids["projector-error"].hidden, waiting: ids.waiting.textContent, waitingHidden: ids.waiting.hidden};
        await ctx.__poll();                                      // open
        out.open = {code: ids.code.textContent, codeHidden: ids.code.hidden, qr: ids.qr.src, waitingHidden: ids.waiting.hidden, stepsHidden: ids.steps.hidden};
        await ctx.__poll();                                      // closed again
        out.closedAgain = {waiting: ids.waiting.textContent, waitingHidden: ids.waiting.hidden, stepsHidden: ids.steps.hidden};
        out.interval = timers[0][1];
      } else {
        const rows = [{nickname: "<b>x</b>", checked_in_at: 1000}];
        responses = [{ok: false, status: 500}, ok({n: 0, head_count: null, consistency: null, check_ins: []}),
                     ok({n: 1, head_count: 3, consistency: "anomaly", check_ins: rows})];
        run(process.argv[3]);
        await new Promise((r) => setTimeout(r, 10));
        out.afterError = {err: ids["attendance-error"].hidden};
        await ctx.__poll();
        out.empty = {err: ids["attendance-error"].hidden, n: ids.n.textContent, d: ids.d.textContent, state: ids.status.dataset.state,
                     rows: ids["attendance-rows"].children.length, text: ids["attendance-rows"].children[0].children[0].textContent};
        await ctx.__poll();
        const td = ids["attendance-rows"].children[0].children[0];
        out.full = {n: ids.n.textContent, d: ids.d.textContent, state: ids.status.dataset.state, status: ids.status.textContent,
                    nick: td.textContent, dir: td.dir};
        out.interval = timers[0][1];
      }
      console.log(JSON.stringify(out));
    })();
""")


def _node(tmp_path, mode, js):
    h = tmp_path / "h.js"
    h.write_text(HARNESS)
    r = subprocess.run([NODE, str(h), mode, str(STATIC / js)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_projector_js_error_then_success_resets_waiting(tmp_path):
    """Covers T22d: error shows #projector-error only; next success hides it and #waiting still reads the text."""
    o = _node(tmp_path, "projector", "projector.js")
    assert o["afterError"]["err"] is False and o["afterError"]["waiting"] == ""  # never written to
    assert o["afterSuccess"] == {"err": True, "waiting": "", "waitingHidden": False}
    assert o["open"] == {"code": "1234", "codeHidden": False, "qr": "data:q", "waitingHidden": True, "stepsHidden": False}
    assert o["closedAgain"]["waitingHidden"] is False and o["closedAgain"]["stepsHidden"] is True
    assert o["interval"] == 1000


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_poll_json_js_behaviour(tmp_path):
    """Covers T22c: error banner then reset, empty-state row, dataset.state, textContent only, dir auto."""
    o = _node(tmp_path, "attendance", "poll_json.js")
    assert o["afterError"]["err"] is False
    assert o["empty"]["err"] is True and o["empty"]["n"] == 0 and o["empty"]["d"] == "—"
    assert o["empty"]["state"] == "none" and o["empty"]["rows"] == 1 and "Nobody has checked in" in o["empty"]["text"]
    assert o["full"]["n"] == 1 and o["full"]["d"] == 3 and o["full"]["state"] == "anomaly"
    assert o["full"]["nick"] == "<b>x</b>" and o["full"]["dir"] == "auto"
    assert o["interval"] == 2500
