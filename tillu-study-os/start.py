#!/usr/bin/env python3
"""
Tillu AI Study OS — single launcher.

Usage:
    python start.py

Starts the FastAPI backend and the Next.js frontend in the correct order.

Exit behaviour:
  - If the backend health probe times out (30 s): print error, kill both, exit 1.
  - If the frontend start times out (60 s after backend ready): print error, kill both, exit 1.
  - On Ctrl+C: SIGTERM both child processes and wait for them to exit.
"""

import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3000"))

HEALTH_URL = f"http://localhost:{BACKEND_PORT}/health"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

BACKEND_TIMEOUT = 30  # seconds to wait for backend /health
FRONTEND_TIMEOUT = 60  # seconds to wait for frontend after backend ready


def _probe(url: str, timeout: float = 2.0) -> bool:
    """Return True if the URL responds with HTTP 200 within timeout seconds."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _wait_for(url: str, timeout: int, label: str) -> bool:
    """Poll url every second until it responds 200 or timeout expires."""
    print(f"  Waiting for {label}…", end="", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _probe(url):
            print(" ready!")
            return True
        print(".", end="", flush=True)
        time.sleep(1)
    print(" timed out!")
    return False


def main() -> None:
    procs: list[subprocess.Popen] = []

    def _terminate_all():
        for p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    def _sigint_handler(sig, frame):
        print("\nShutting down Tillu…")
        _terminate_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)

    # ── 1. Start backend ────────────────────────────────────────────────────
    print("Starting FastAPI backend…")
    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", str(BACKEND_PORT),
        "--reload",
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(BACKEND_DIR),
        env={**os.environ},
    )
    procs.append(backend_proc)

    if not _wait_for(HEALTH_URL, BACKEND_TIMEOUT, "backend"):
        print(f"ERROR: Backend did not become healthy within {BACKEND_TIMEOUT}s.")
        _terminate_all()
        sys.exit(1)

    # ── 2. Start frontend ────────────────────────────────────────────────────
    print("Starting Next.js frontend…")
    frontend_cmd = ["npm", "run", "dev", "--", "--port", str(FRONTEND_PORT)]
    # On Windows npm is a .cmd file
    if sys.platform == "win32":
        frontend_cmd = ["npm.cmd", "run", "dev", "--", "--port", str(FRONTEND_PORT)]

    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR),
        env={**os.environ},
    )
    procs.append(frontend_proc)

    if not _wait_for(FRONTEND_URL, FRONTEND_TIMEOUT, "frontend"):
        print(f"ERROR: Frontend did not start within {FRONTEND_TIMEOUT}s.")
        _terminate_all()
        sys.exit(1)

    # ── 3. Both ready ────────────────────────────────────────────────────────
    print(f"\n✓ Tillu AI Study OS is running!")
    print(f"  Dashboard : {FRONTEND_URL}")
    print(f"  Backend   : http://localhost:{BACKEND_PORT}")
    print(f"  API docs  : http://localhost:{BACKEND_PORT}/docs")
    print("\nPress Ctrl+C to stop.\n")

    # Block until a child exits or Ctrl+C
    try:
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"A process exited unexpectedly (code {p.returncode}). Shutting down.")
                    _terminate_all()
                    sys.exit(p.returncode or 1)
            time.sleep(1)
    except KeyboardInterrupt:
        _sigint_handler(None, None)


if __name__ == "__main__":
    main()
