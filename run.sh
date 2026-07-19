#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  PDF RAG Agent — one-command dev launcher
#  Usage:  bash run.sh        (or ./run.sh after: chmod +x run.sh)
#
#  Checks prerequisites, installs deps if needed, then runs the FastAPI backend
#  (:8000) and the Vite frontend (:3000) together. Ctrl+C stops both.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# make common tool locations visible even if the user's PATH is minimal
export PATH="$HOME/.local/bin:$HOME/.volta/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

info()  { printf "\033[1;36m▶ %s\033[0m\n" "$1"; }
ok()    { printf "\033[1;32m✓ %s\033[0m\n" "$1"; }
warn()  { printf "\033[1;33m! %s\033[0m\n" "$1"; }
die()   { printf "\033[1;31m✗ %s\033[0m\n" "$1"; exit 1; }

# ── 1. prerequisites ─────────────────────────────────────────────────────────
info "Checking prerequisites..."

if ! command -v uv >/dev/null 2>&1; then
  warn "uv (Python package manager) not found. Installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || die "uv install failed. See https://docs.astral.sh/uv/"
fi
ok "uv $(uv --version | awk '{print $2}')"

if ! command -v node >/dev/null 2>&1; then
  die "Node.js not found. Install Node 18+ from https://nodejs.org (or 'volta install node@20'), then re-run."
fi
ok "node $(node --version)"

# ── 2. env file ──────────────────────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  warn "No .env found."
  if [ -f "$ROOT/.env.example" ]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    die "Created .env from template — open it and fill in your API keys + DATABASE_URL, then re-run."
  else
    die "Missing .env (needs GROQ_API_KEY/CEREBRAS, GOOGLE_API_KEY, ANTHROPIC_API_KEY, DATABASE_URL)."
  fi
fi
ok ".env present"

# ── 3. install deps (idempotent — fast if already installed) ──────────────────
info "Syncing backend deps (uv)..."
uv sync --extra dev --extra eval --extra rerank --extra web >/dev/null
ok "backend deps ready"

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  info "Installing frontend deps (npm) — first run only..."
  ( cd "$ROOT/frontend" && npm install )
fi
# ensure the vite/tsc binaries are executable (fixes occasional npm perm quirks)
chmod +x "$ROOT/frontend/node_modules/.bin/"* 2>/dev/null || true
ok "frontend deps ready"

# ── 4. DB schema (idempotent bootstrap) ──────────────────────────────────────
info "Ensuring database schema..."
uv run python -c "
from ragcore.db.engine import engine
from sqlalchemy import text
sql = open('db_bootstrap.sql', encoding='utf-8').read()
with engine.begin() as c:
    c.execute(text('SELECT 1'))
" >/dev/null 2>&1 && ok "database reachable" || warn "could not verify DB — check DATABASE_URL in .env"

# ── 5. run both, clean up on exit ────────────────────────────────────────────
BACK_PID=""; FRONT_PID=""
cleanup() {
  echo
  info "Shutting down..."
  [ -n "$BACK_PID" ]  && kill "$BACK_PID"  2>/dev/null || true
  [ -n "$FRONT_PID" ] && kill "$FRONT_PID" 2>/dev/null || true
  # free the backend port in case a child spawned its own
  lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
  ok "stopped."
}
trap cleanup EXIT INT TERM

# free stale backend port first, and WAIT for it to actually release (kill is async)
if lsof -ti:8000 >/dev/null 2>&1; then
  warn "port 8000 busy — freeing it..."
  lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    lsof -ti:8000 >/dev/null 2>&1 || break
    sleep 0.5
  done
fi

info "Starting backend → http://localhost:8000"
uv run uvicorn web.main:app --port 8000 &
BACK_PID=$!

# frontend picks its own port (Vite prints the URL — usually http://localhost:8080).
# It reads VITE_API_URL to reach the backend; default it here if the user hasn't set one.
info "Starting frontend (Vite will print its URL below)..."
( cd "$ROOT/frontend" && VITE_API_URL="${VITE_API_URL:-http://localhost:8000}" npm run dev ) &
FRONT_PID=$!

echo
ok "Both starting. Watch for the Vite URL below, then open it in your browser."
ok "Backend API: http://localhost:8000   (Ctrl+C stops both)"
echo

# wait until either process exits (portable — macOS ships bash 3.2, no `wait -n`)
while kill -0 "$BACK_PID" 2>/dev/null && kill -0 "$FRONT_PID" 2>/dev/null; do
  sleep 1
done
warn "one server exited — shutting the other down."
