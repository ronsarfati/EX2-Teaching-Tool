"""Tests for scripts/HereOrNot.command (decision D39). No real tunnel, no network.

Covers D39 (launcher: prerequisites check, tunnel URL parsing, app start with env vars, clean shutdown,
already-running path, no secret in the output).

The script is never edited. Tests that must not touch the real repo run a copy of it inside a temporary
"mini repo" (scripts/, a symlinked .venv and app, a dummy .env), because the script resolves its root from its
own location.
"""
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "HereOrNot.command"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or BASH is None, reason="the launcher is a macOS bash script"
)

SECRETS = {
    "SECRET_KEY": "SENTINEL-secret-key-9f3a",
    "LECTURER_PIN": "SENTINEL-pin-7c21",
    "ANTHROPIC_API_KEY": "SENTINEL-anthropic-5e88",
}
SYSTEM_PATH = "/usr/bin:/bin"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_repo(tmp_path: Path, *, env_file: bool = True, strip_path_export: bool = False) -> Path:
    """Mini repo: scripts/HereOrNot.command (copy), .venv and app symlinked to the real ones, dummy .env."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    text = SCRIPT.read_text()
    if strip_path_export:  # the script appends Homebrew dirs to PATH; drop that to simulate a bare machine
        text = "\n".join(l for l in text.splitlines() if not l.startswith('export PATH="$PATH:'))
    dest = root / "scripts" / "HereOrNot.command"
    dest.write_text(text)
    dest.chmod(0o755)
    (root / ".venv").symlink_to(REPO / ".venv")
    (root / "app").symlink_to(REPO / "app")
    if env_file:
        lines = [f"{k}=file-{v}" for k, v in SECRETS.items()] + ["BASE_URL=http://wrong.invalid"]
        (root / ".env").write_text("\n".join(lines) + "\n")
    return root


def make_stub(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(exist_ok=True)
    path = directory / name
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)
    return path


def run_check(root: Path, path: str, extra_env=None):
    env = {"PATH": path, "HOME": str(root), "TMPDIR": str(root)}
    env.update(extra_env or {})
    return subprocess.run(
        [BASH, str(root / "scripts" / "HereOrNot.command"), "--check"],
        capture_output=True, text=True, timeout=30, env=env,
    )


def has_homebrew_tools() -> bool:
    env_path = os.environ["PATH"] + ":/opt/homebrew/bin:/usr/local/bin"
    return bool(shutil.which("cloudflared", path=env_path) and shutil.which("ffmpeg", path=env_path))


# ---------------------------------------------------------------- --check

@pytest.mark.skipif(not has_homebrew_tools(), reason="cloudflared/ffmpeg not installed")
def test_check_ok_in_real_repo():
    """Covers D39: --check exits 0 in the real repo (needs .venv, cloudflared, ffmpeg, .env)."""
    if not (REPO / ".env").exists():
        pytest.skip("no local .env")
    r = subprocess.run([BASH, str(SCRIPT), "--check"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_check_fails_without_cloudflared(tmp_path):
    """Covers D39: missing cloudflared -> exit 1 with install hint (script copy without the Homebrew PATH export)."""
    root = make_repo(tmp_path, strip_path_export=True)
    r = run_check(root, SYSTEM_PATH)
    assert r.returncode == 1
    assert "cloudflared not found" in r.stderr and "brew install cloudflared" in r.stderr


def test_check_fails_without_ffmpeg(tmp_path):
    """Covers D39: missing ffmpeg -> exit 1 with install hint."""
    root = make_repo(tmp_path, strip_path_export=True)
    stubs = tmp_path / "stubs"
    make_stub(stubs, "cloudflared", "exit 0\n")
    r = run_check(root, f"{stubs}:{SYSTEM_PATH}")
    assert r.returncode == 1
    assert "ffmpeg not found" in r.stderr


def test_check_fails_without_env_file(tmp_path):
    """Covers D39: missing .env -> exit 1 with a clear message (the real .env is untouched)."""
    root = make_repo(tmp_path, env_file=False, strip_path_export=True)
    stubs = tmp_path / "stubs"
    make_stub(stubs, "cloudflared", "exit 0\n")
    make_stub(stubs, "ffmpeg", "exit 0\n")
    r = run_check(root, f"{stubs}:{SYSTEM_PATH}")
    assert r.returncode == 1
    assert ".env not found" in r.stderr and ".env.example" in r.stderr


def test_check_fails_without_venv(tmp_path):
    """Covers D39: missing .venv -> exit 1 with the creation command."""
    root = make_repo(tmp_path, strip_path_export=True)
    (root / ".venv").unlink()
    r = run_check(root, SYSTEM_PATH)
    assert r.returncode == 1
    assert ".venv not found" in r.stderr


def test_check_passes_with_stubs_and_prints_no_secret(tmp_path):
    """Covers D39: --check succeeds on a complete mini repo and never prints secret values."""
    root = make_repo(tmp_path, strip_path_export=True)
    stubs = tmp_path / "stubs"
    make_stub(stubs, "cloudflared", "exit 0\n")
    make_stub(stubs, "ffmpeg", "exit 0\n")
    r = run_check(root, f"{stubs}:{SYSTEM_PATH}", SECRETS)
    assert r.returncode == 0
    assert "SENTINEL" not in r.stdout + r.stderr


# ---------------------------------------------------------------- already running

class _Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def test_already_running_exits_zero_quickly(tmp_path):
    """Covers D39: if /ping already answers on PORT, the script says so and exits 0 without starting anything."""
    root = make_repo(tmp_path)
    port = free_port()
    server = HTTPServer(("127.0.0.1", port), _Ping)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stubs = tmp_path / "stubs"
    marker = tmp_path / "tunnel_started"
    make_stub(stubs, "cloudflared", f"touch {marker}\nexit 0\n")
    make_stub(stubs, "ffmpeg", "exit 0\n")
    try:
        start = time.time()
        r = subprocess.run(
            [BASH, str(root / "scripts" / "HereOrNot.command")],
            capture_output=True, text=True, timeout=20,
            env={"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(root), "TMPDIR": str(root),
                 "PORT": str(port), "HEREORNOT_NO_OPEN": "1", **SECRETS},
        )
    finally:
        server.shutdown()
    assert r.returncode == 0, r.stderr
    assert "already running" in r.stdout
    assert time.time() - start < 10
    assert not marker.exists(), "the tunnel must not be started when the app already runs"
    assert "SENTINEL" not in r.stdout + r.stderr


# ---------------------------------------------------------------- full start / stop

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _listening_pids(port: int) -> list[int]:
    out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
    return [int(x) for x in out.split()]


@pytest.mark.skipif(shutil.which("lsof") is None, reason="lsof needed")
def test_full_start_parses_url_and_shuts_down_cleanly(tmp_path):
    """Covers D39: stub tunnel URL is parsed and shown, app starts on PORT with env vars (env wins over .env),
    /ping answers, SIGTERM leaves no process and no temp log, and no secret is printed."""
    root = make_repo(tmp_path)
    port = free_port()
    stubs = tmp_path / "stubs"
    args_file = tmp_path / "tunnel_args"
    url = "https://x-y.trycloudflare.com"
    # The real script waits for the public URL to answer /ping; a curl stub answers it locally (no network).
    real_curl = shutil.which("curl")
    make_stub(stubs, "curl", f'case "$*" in *trycloudflare.com*) exit 0;; esac\nexec {real_curl} "$@"\n')
    make_stub(stubs, "ffmpeg", "exit 0\n")
    make_stub(
        stubs, "cloudflared",
        f'echo "$@" > {args_file}\n'
        f'echo "INF |  {url}  |"\n'
        "exec sleep 4321\n",
    )
    # BSD mktemp -t ignores $TMPDIR (it uses the per-user temp dir), so compare with that directory.
    tmpdir = Path(subprocess.run(["getconf", "DARWIN_USER_TEMP_DIR"], capture_output=True, text=True).stdout.strip())
    before = set(tmpdir.glob("hereornot-*"))
    db = tmp_path / "db" / "t.sqlite"
    db.parent.mkdir()
    out_file = tmp_path / "out.txt"
    env = {
        "PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(root), "TMPDIR": str(tmp_path),
        "PORT": str(port), "HEREORNOT_NO_OPEN": "1", "DATABASE_PATH": str(db), "BASE_URL": "http://ignored.invalid",
        **SECRETS,
    }
    with open(out_file, "w") as out:
        proc = subprocess.Popen(
            [BASH, str(root / "scripts" / "HereOrNot.command")],
            stdout=out, stderr=subprocess.STDOUT, env=env, cwd=tmp_path,
        )
    app_pids: list[int] = []
    try:
        deadline = time.time() + 60
        while time.time() < deadline and "HereOrNot is running" not in out_file.read_text():
            assert proc.poll() is None, out_file.read_text()
            time.sleep(0.3)
        text = out_file.read_text()
        assert "HereOrNot is running" in text, text
        assert f"Public URL for phones: {url}" in text
        assert f"http://localhost:{port}/lecturer/login" in text
        assert "--url" in args_file.read_text() and f"http://127.0.0.1:{port}" in args_file.read_text()

        ping = subprocess.run(["curl", "-fsS", f"http://127.0.0.1:{port}/ping"], capture_output=True, text=True)
        assert ping.returncode == 0, ping.stderr
        app_pids = _listening_pids(port)
        assert app_pids
        assert set(tmpdir.glob("hereornot-*")) - before, "temp logs should exist while running"
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise

    assert proc.returncode == 130
    time.sleep(1)
    assert not any(_pid_alive(p) for p in app_pids), "app process left behind"
    assert _listening_pids(port) == []
    leftover = subprocess.run(["pgrep", "-f", "sleep 4321"], capture_output=True, text=True).stdout.strip()
    assert leftover == "", "stub tunnel left behind"
    assert set(tmpdir.glob("hereornot-*")) - before == set(), "temp logs not removed"
    text = out_file.read_text()
    assert "SENTINEL" not in text
    assert re.search(r"https://[A-Za-z0-9-]+\.trycloudflare\.com", text)
