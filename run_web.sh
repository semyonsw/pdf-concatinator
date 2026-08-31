#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Starts the PDF Concatenator: the API engine plus the browser interface.
#  Press Ctrl+C to stop both.
#
#  Run ./install.sh first - it creates the .venv/ this script uses.
# ---------------------------------------------------------------------------
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PY="$ROOT_DIR/.venv/bin/python"
RED=$'\033[31m'; GRN=$'\033[32m'; DIM=$'\033[2m'; RST=$'\033[0m'

fail() { printf '\n%s  %s%s\n\n' "$RED" "$1" "$RST"; shift; for l in "$@"; do printf '  %s\n' "$l"; done; printf '\n'; exit 1; }

[ -x "$PY" ] || fail 'This project is not installed yet.' \
    'Run the installer first:' '    ./install.sh'
[ -d "$ROOT_DIR/frontend/node_modules" ] || fail 'The browser interface is not installed yet.' \
    'Run the installer first:' '    ./install.sh'

mkdir -p .web_data
BACKEND_LOG="$ROOT_DIR/.web_data/backend.log"

if command -v curl >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    fail 'Something is already listening on port 8000.' \
        'Another copy of this app is probably running. Close it, or find it with:' \
        '    ss -ltnp | grep :8000'
fi

printf '  Starting the engine on http://127.0.0.1:8000\n'
"$PY" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000 >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

cleanup() { kill "$BACKEND_PID" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

printf '  Waiting for it to answer...\n'
for _ in $(seq 1 60); do
    if command -v curl >/dev/null 2>&1; then
        curl -fsS "http://127.0.0.1:8000/api/health" >/dev/null 2>&1 && break
    else
        "$PY" - <<'PROBE' >/dev/null 2>&1 && break
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
PROBE
    fi
    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
        printf '\n%s  The engine stopped straight away. Its last words:%s\n\n' "$RED" "$RST"
        tail -n 25 "$BACKEND_LOG" || true
        printf '\n  Full log: %s\n\n' "$BACKEND_LOG"
        exit 1
    fi
    sleep 0.5
done

printf '%s  Engine ready.%s  %s(log: %s)%s\n' "$GRN" "$RST" "$DIM" "$BACKEND_LOG" "$RST"
printf '  Opening the interface on http://localhost:5173 - press Ctrl+C here to stop everything.\n\n'

npm --prefix frontend run dev -- --open
