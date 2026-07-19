#!/usr/bin/env python3
"""PDF RAG Agent — cross-platform one-command launcher (macOS / Linux / Windows).

Starts the FastAPI backend (:8000) and the Vite frontend together, and stops both on
Ctrl+C. Python is already required by the backend, so this single file works everywhere —
no separate .sh / .bat / .ps1 to keep in sync.

Usage:
    python run.py          (Windows)
    python3 run.py         (macOS / Linux)
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
IS_WINDOWS = os.name == "nt"

# make common tool locations visible even on a minimal PATH
_extra = [
    Path.home() / ".local" / "bin",
    Path.home() / ".volta" / "bin",
    Path.home() / ".cargo" / "bin",
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
]
os.environ["PATH"] = os.pathsep.join(
    [str(p) for p in _extra if p.exists()] + [os.environ.get("PATH", "")]
)


def c(msg: str, color: str = "36") -> None:
    print(f"\033[1;{color}m{msg}\033[0m", flush=True)


def info(m): c(f"> {m}", "36")
def ok(m):   c(f"[OK] {m}", "32")
def warn(m): c(f"[!] {m}", "33")
def die(m):
    c(f"[X] {m}", "31")
    sys.exit(1)


def have(tool: str) -> str | None:
    """Return the resolved path to a CLI tool, or None. (shutil.which is cross-platform.)"""
    return shutil.which(tool)


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def free_port(port: int) -> None:
    """Best-effort: kill whatever holds `port` (OS-specific)."""
    try:
        if IS_WINDOWS:
            out = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True
            ).stdout
            pids = {
                line.split()[-1]
                for line in out.splitlines()
                if f":{port}" in line and "LISTENING" in line
            }
            for pid in pids:
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True)
        else:
            out = subprocess.run(
                ["lsof", f"-ti:{port}"], capture_output=True, text=True
            ).stdout
            for pid in out.split():
                subprocess.run(["kill", "-9", pid], capture_output=True)
    except Exception:
        pass


# ── 1. prerequisites ─────────────────────────────────────────────────────────
info("Checking prerequisites...")

if not have("uv"):
    warn("uv (Python package manager) not found.")
    if IS_WINDOWS:
        die('Install uv, then re-run:\n'
            '  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"')
    else:
        warn("Installing uv...")
        subprocess.run("curl -LsSf https://astral.sh/uv/install.sh | sh",
                       shell=True, check=False)
        os.environ["PATH"] = f"{Path.home()/'.local'/'bin'}{os.pathsep}{os.environ['PATH']}"
        if not have("uv"):
            die("uv install failed. See https://docs.astral.sh/uv/")
ok("uv found")

if not have("node"):
    die("Node.js not found. Install Node 18+ from https://nodejs.org , then re-run.")
ok(f"node {subprocess.run(['node','--version'],capture_output=True,text=True).stdout.strip()}")

# ── 2. .env ──────────────────────────────────────────────────────────────────
if not (ROOT / ".env").exists():
    if (ROOT / ".env.example").exists():
        shutil.copy(ROOT / ".env.example", ROOT / ".env")
        die("Created .env from template — open it, fill in your API keys + DATABASE_URL, then re-run.")
    die("Missing .env (needs GOOGLE_API_KEY, DATABASE_URL, etc.).")
ok(".env present")

# ── 3. deps (idempotent) ─────────────────────────────────────────────────────
info("Syncing backend deps (uv)...")
subprocess.run(["uv", "sync", "--extra", "dev", "--extra", "eval",
                "--extra", "rerank", "--extra", "web"], cwd=ROOT, check=True)
ok("backend deps ready")

if not (FRONTEND / "node_modules").exists():
    info("Installing frontend deps (npm) — first run only...")
    subprocess.run(["npm", "install"], cwd=FRONTEND, check=True, shell=IS_WINDOWS)
ok("frontend deps ready")

# ── 4. run both ──────────────────────────────────────────────────────────────
if port_busy(8000):
    warn("port 8000 busy — freeing it...")
    free_port(8000)
    for _ in range(10):
        if not port_busy(8000):
            break
        time.sleep(0.5)

procs: list[subprocess.Popen] = []


def shutdown(*_):
    print()
    info("Shutting down...")
    for p in procs:
        try:
            if IS_WINDOWS:
                p.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                p.terminate()
        except Exception:
            pass
    for p in procs:
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    free_port(8000)
    ok("stopped.")
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

create_flags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0

info("Starting backend -> http://localhost:8000")
procs.append(subprocess.Popen(
    ["uv", "run", "uvicorn", "web.main:app", "--port", "8000"],
    cwd=ROOT, creationflags=create_flags,
))

env = {**os.environ, "VITE_API_URL": os.environ.get("VITE_API_URL", "http://localhost:8000")}
info("Starting frontend (Vite will print its URL below)...")
procs.append(subprocess.Popen(
    ["npm", "run", "dev"], cwd=FRONTEND, env=env,
    shell=IS_WINDOWS, creationflags=create_flags,
))

print()
ok("Both starting. Open the Vite URL printed below (usually http://localhost:8080).")
ok("Backend API: http://localhost:8000    (Ctrl+C stops both)")
print()

# wait until either exits, then shut the other down (portable)
try:
    while all(p.poll() is None for p in procs):
        time.sleep(1)
    warn("one server exited — shutting the other down.")
    shutdown()
except KeyboardInterrupt:
    shutdown()
