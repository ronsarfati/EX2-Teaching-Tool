#!/usr/bin/env bash
# HereOrNot launcher: one double-click starts the tunnel and the app, then opens the lecturer page.
# Usage: HereOrNot.command [--check]   (--check only verifies the prerequisites, then exits)
# Set HEREORNOT_NO_OPEN=1 to skip opening Safari (used by tests).

# Finder does not load the shell profile, so Homebrew tools are missing from PATH.
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"

# Resolve the real script location even through a symlink (e.g. on the Desktop).
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
ROOT="$(cd -P "$(dirname "$SOURCE")/.." && pwd)"
cd "$ROOT" || exit 1

PORT="${PORT:-5050}"
TUNNEL_WAIT=45
APP_WAIT=30

fail() { echo "ERROR: $*" >&2; exit 1; }

check_prerequisites() {
  [ -x "$ROOT/.venv/bin/python" ] || fail ".venv not found. Create it: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  command -v cloudflared >/dev/null || fail "cloudflared not found. Install it: brew install cloudflared"
  command -v ffmpeg >/dev/null || fail "ffmpeg not found. Install it: brew install ffmpeg"
  [ -f "$ROOT/.env" ] || fail ".env not found. Copy .env.example to .env and fill it in."
}

check_prerequisites
if [ "${1:-}" = "--check" ]; then
  echo "OK: .venv, cloudflared, ffmpeg and .env are present."
  exit 0
fi

# Succeeds when the given base URL answers /ping.
pings() { curl -fsS --max-time 3 "$1/ping" >/dev/null 2>&1; }

open_safari() {
  [ -n "${HEREORNOT_NO_OPEN:-}" ] || open -a Safari "http://localhost:$PORT/lecturer/login"
}

if pings "http://127.0.0.1:$PORT"; then
  echo "HereOrNot is already running (port $PORT). Opening Safari."
  open_safari
  exit 0
fi

TUNNEL_LOG="$(mktemp -t hereornot-tunnel)"
APP_LOG="$(mktemp -t hereornot-app)"
TUNNEL_PID=""
APP_PID=""

cleanup() {
  trap - EXIT INT TERM HUP
  [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null
  [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null
  rm -f "$TUNNEL_LOG" "$APP_LOG"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

echo "Starting the tunnel..."
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

PUBLIC_URL=""
for _ in $(seq "$TUNNEL_WAIT"); do
  PUBLIC_URL="$(grep -Eo 'https://[A-Za-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -n 1)"
  [ -n "$PUBLIC_URL" ] && break
  kill -0 "$TUNNEL_PID" 2>/dev/null || break
  sleep 1
done

if [ -z "$PUBLIC_URL" ]; then
  echo "WARNING: no tunnel URL after ${TUNNEL_WAIT}s. Plan B: use your phone hotspot (see docs/demo_script.md)."
  echo "Continuing with http://localhost:$PORT only."
  kill "$TUNNEL_PID" 2>/dev/null
  TUNNEL_PID=""
  BASE_URL="http://localhost:$PORT"
else
  BASE_URL="$PUBLIC_URL"
fi

# Exported only for the app process: .env stays untouched and environment variables win over it.
echo "Starting the app..."
BASE_URL="$BASE_URL" PORT="$PORT" "$ROOT/.venv/bin/python" -m app >"$APP_LOG" 2>&1 &
APP_PID=$!

for _ in $(seq "$APP_WAIT"); do
  pings "http://127.0.0.1:$PORT" && break
  kill -0 "$APP_PID" 2>/dev/null || break
  sleep 1
done
if ! pings "http://127.0.0.1:$PORT"; then
  echo "App log (last lines):" >&2
  tail -n 15 "$APP_LOG" >&2
  fail "the app did not answer /ping within ${APP_WAIT}s."
fi

if [ -n "$PUBLIC_URL" ]; then
  echo "Waiting for the tunnel to reach the app..."
  for _ in $(seq "$APP_WAIT"); do
    pings "$PUBLIC_URL" && break
    sleep 1
  done
  pings "$PUBLIC_URL" || echo "WARNING: $PUBLIC_URL does not answer /ping yet; phones may need a few more seconds."
fi

open_safari

echo
echo "=== HereOrNot is running ==="
echo "Public URL for phones: $BASE_URL"
echo "Lecturer page:         http://localhost:$PORT/lecturer/login"
echo "Keep this window open. Press Ctrl+C or close the window to stop."

# Stop (and clean up) as soon as either process dies.
while kill -0 "$APP_PID" 2>/dev/null && { [ -z "$TUNNEL_PID" ] || kill -0 "$TUNNEL_PID" 2>/dev/null; }; do
  sleep 1
done
echo "A process stopped unexpectedly; shutting down."
exit 1
