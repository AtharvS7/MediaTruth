#!/usr/bin/env python3
"""
MediaTruth — Unified Dev Server Launcher
=========================================
Run this single file to start both the FastAPI backend and Next.js frontend
simultaneously, wait for both to be ready, and open the browser automatically.

Usage:
    python start.py

Requirements:
    - Python 3.9+  (for this script itself)
    - Node.js 18+  with npm  (for the frontend)
    - Backend virtual environment at backend/venv or backend/.venv
    - frontend/node_modules installed (runs npm install automatically if missing)

Platform support: Windows, macOS, Linux
"""

import os
import sys
import time
import shutil
import signal
import threading
import subprocess
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# Force UTF-8 output on Windows to support any Unicode characters
# Without this, printing non-ASCII to cp1252 consoles raises UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR    = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

BACKEND_PORT   = 8000
FRONTEND_PORT  = 3000
BACKEND_URL    = f"http://localhost:{BACKEND_PORT}"
FRONTEND_URL   = f"http://localhost:{FRONTEND_PORT}"
HEALTH_URL     = f"{BACKEND_URL}/health/"

# How long to wait (seconds) for each service to become healthy
# NOTE: Backend timeout is 180s because on first run it downloads ~300MB of
# EfficientNet-B5 weights from HuggingFace. Subsequent starts are 30-60s.
BACKEND_TIMEOUT  = 180
FRONTEND_TIMEOUT = 120

# ─────────────────────────────────────────────────────────────────────────────
# Terminal Colors (ANSI escape codes — work on Windows 10+ with VT support)
# ─────────────────────────────────────────────────────────────────────────────

IS_WIN = sys.platform == "win32"

# On Windows, npm is a .cmd batch file, not an .exe.
# subprocess cannot locate it with just "npm" — must use "npm.cmd" or shell=True.
NPM_CMD = "npm.cmd" if IS_WIN else "npm"

# Enable VT processing on Windows (needed for ANSI colors in cmd.exe / PowerShell)
if IS_WIN:
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
WHITE  = "\033[97m"
DIM    = "\033[2m"
MAGENTA = "\033[95m"

def c(color: str, text: str) -> str:
    """Wrap text in ANSI color escape."""
    return f"{color}{text}{RESET}"

def banner():
    """Print the MediaTruth ASCII banner."""
    print()
    print(c(CYAN,  "  +-+-+-+-+-+-+-+-+-+-+"))
    print(c(CYAN,  "  | M E D I A T R U T H |"))
    print(c(WHITE, "  +-+-+-+-+-+-+-+-+-+-+"))
    print()
    print(c(CYAN,  "  ###  ###  #####  ####  ###    ##  ####  ####  ##  ##  ####  ##  ##"))
    print(c(WHITE, "  ## ## ## ##     ##  ## ##  ##  ## ##  ## ##  ## ## ##  ##  ## ## ## "))
    print(c(WHITE, "  ## ## ## #####  ##  ## #####   ## ###### ##  ## ##     ##  ## ## ##"))
    print(c(CYAN,  "  ##    ## ###### ######  ## ## #### ##  ## ####  ##     ##  ##  ###"))
    print()
    print(c(DIM,   "  AI Media Forensics Platform -- Dev Server Launcher"))
    print()

def log(prefix: str, color: str, msg: str):
    """Print a colored, timestamped log line."""
    ts = time.strftime("%H:%M:%S")
    print(f"  {c(DIM, ts)}  {c(color + BOLD, prefix):30s}  {msg}")

def log_backend(msg: str):
    log("[BACKEND]", CYAN, msg)

def log_frontend(msg: str):
    log("[FRONTEND]", MAGENTA, msg)

def log_launcher(msg: str):
    log("[LAUNCHER]", GREEN, msg)

def log_error(msg: str):
    log("[ERROR]", RED, msg)

def log_warn(msg: str):
    log("[WARN]", YELLOW, msg)

# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight Checks
# ─────────────────────────────────────────────────────────────────────────────

def check_node() -> bool:
    """Verify Node.js and npm are available."""
    if not shutil.which("node") and not shutil.which("node.exe"):
        log_error("Node.js not found. Install from https://nodejs.org (v18+)")
        return False
    # On Windows npm is npm.cmd; shutil.which finds it via PATHEXT
    if not shutil.which("npm") and not shutil.which("npm.cmd"):
        log_error("npm not found. Install Node.js from https://nodejs.org")
        return False
    try:
        node_ver = subprocess.check_output(
            ["node", "--version"], text=True, shell=IS_WIN
        ).strip()
        npm_ver = subprocess.check_output(
            [NPM_CMD, "--version"], text=True, shell=IS_WIN
        ).strip()
        log_launcher(f"Node.js {node_ver} / npm {npm_ver} ✓")
    except Exception as e:
        log_error(f"Could not determine Node/npm version: {e}")
        return False
    return True


def find_venv() -> Optional[Path]:
    """Find the backend virtual environment directory."""
    for candidate in ["venv", ".venv", "env", ".env"]:
        p = BACKEND_DIR / candidate
        if p.is_dir():
            return p
    return None


def get_python_executable(venv: Path) -> Path:
    """Return the Python executable inside the virtual environment."""
    if IS_WIN:
        return venv / "Scripts" / "python.exe"
    else:
        return venv / "bin" / "python"


def get_uvicorn_executable(venv: Path) -> Path:
    """Return the uvicorn executable inside the virtual environment."""
    if IS_WIN:
        return venv / "Scripts" / "uvicorn.exe"
    else:
        return venv / "bin" / "uvicorn"


def check_backend_env() -> tuple[Optional[Path], Optional[Path]]:
    """Check backend venv exists and return (venv_dir, uvicorn_path)."""
    venv = find_venv()
    if not venv:
        log_error(
            f"No virtual environment found in {BACKEND_DIR}. "
            "Create one with: python -m venv backend/venv && "
            "backend/venv/Scripts/pip install -r backend/requirements.txt"
        )
        return None, None

    uvicorn = get_uvicorn_executable(venv)
    if not uvicorn.exists():
        log_error(
            f"uvicorn not found at {uvicorn}. "
            "Install it with: backend/venv/Scripts/pip install -r backend/requirements.txt"
        )
        return venv, None

    log_launcher(f"Virtual environment: {venv} ✓")
    log_launcher(f"uvicorn: {uvicorn} ✓")
    return venv, uvicorn


def check_backend_env_file() -> bool:
    """Check that the backend .env file exists."""
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        example = BACKEND_DIR / ".env.example"
        if example.exists():
            log_warn(
                f"backend/.env not found. "
                "Copying .env.example → .env (fill in real Supabase credentials!)"
            )
            import shutil
            shutil.copy(example, env_file)
        else:
            log_error(
                "backend/.env not found. Create it with your Supabase credentials. "
                "See backend/.env.example for the required variables."
            )
            return False
    return True


def check_frontend_env_file() -> bool:
    """Check that the frontend .env.local file exists."""
    env_file = FRONTEND_DIR / ".env.local"
    if not env_file.exists():
        example = FRONTEND_DIR / ".env.local.example"
        if example.exists():
            log_warn("frontend/.env.local not found. Copying .env.local.example → .env.local")
            import shutil
            shutil.copy(example, env_file)
        else:
            log_warn(
                "frontend/.env.local not found. "
                "Create it with NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, "
                "and NEXT_PUBLIC_API_URL=http://localhost:8000"
            )
    return True


def ensure_node_modules() -> bool:
    """Run npm install if node_modules is missing."""
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        log_launcher("node_modules not found — running npm install (this may take a minute)...")
        result = subprocess.run(
            [NPM_CMD, "install"],
            cwd=FRONTEND_DIR,
            capture_output=False,
            shell=IS_WIN,  # Required on Windows for .cmd scripts
        )
        if result.returncode != 0:
            log_error("npm install failed. Check your Node.js version and network connection.")
            return False
        log_launcher("npm install complete ✓")
    else:
        log_launcher("node_modules present ✓")
    return True

# ─────────────────────────────────────────────────────────────────────────────
# Process Launchers
# ─────────────────────────────────────────────────────────────────────────────

class ColoredOutputThread(threading.Thread):
    """
    Background thread that reads from a process stream
    and prints each line with a colored prefix.
    """

    def __init__(self, stream, label_fn, filter_fn=None):
        super().__init__(daemon=True)
        self.stream = stream
        self.label_fn = label_fn
        self.filter_fn = filter_fn or (lambda line: True)
        self.ready_event = threading.Event()
        self.ready_keywords: list[str] = []

    def run(self):
        try:
            for raw_line in iter(self.stream.readline, b""):
                try:
                    line = raw_line.decode("utf-8", errors="replace").rstrip()
                except Exception:
                    line = repr(raw_line)
                if line:
                    self.label_fn(line)
                    # Check for readiness signals
                    for kw in self.ready_keywords:
                        if kw.lower() in line.lower():
                            self.ready_event.set()
        except Exception:
            pass


def start_backend(uvicorn: Path) -> Optional[subprocess.Popen]:
    """Launch the FastAPI backend with uvicorn."""
    log_backend(f"Starting FastAPI backend on port {BACKEND_PORT}...")

    cmd = [
        str(uvicorn),
        "main:app",
        "--host", "0.0.0.0",
        "--port", str(BACKEND_PORT),
        "--reload",
        "--reload-dir", str(BACKEND_DIR),
        "--log-level", "info",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=BACKEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr into stdout
            bufsize=0,
        )

        reader = ColoredOutputThread(proc.stdout, log_backend)
        reader.ready_keywords = ["application startup complete", "uvicorn running"]
        reader.start()

        return proc
    except Exception as e:
        log_error(f"Failed to start backend: {e}")
        return None


def start_frontend() -> Optional[subprocess.Popen]:
    """Launch the Next.js dev server."""
    log_frontend(f"Starting Next.js frontend on port {FRONTEND_PORT}...")

    # On Windows, npm.cmd requires shell=True to be found by subprocess
    npm_run_dev = [NPM_CMD, "run", "dev"]

    try:
        proc = subprocess.Popen(
            npm_run_dev,
            cwd=FRONTEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            shell=IS_WIN,  # Required on Windows: npm.cmd is a batch file
            env={**os.environ, "PORT": str(FRONTEND_PORT)},
        )

        reader = ColoredOutputThread(proc.stdout, log_frontend)
        reader.ready_keywords = ["ready", "started server", "local:", "localhost"]
        reader.start()

        return proc
    except Exception as e:
        log_error(f"Failed to start frontend: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Health Checks
# ─────────────────────────────────────────────────────────────────────────────

def wait_for_backend(timeout: int = BACKEND_TIMEOUT) -> bool:
    """Poll /health/ until the backend returns HTTP 200 or timeout."""
    log_backend(f"Waiting for backend to become ready (up to {timeout}s)...")
    log_backend(c(DIM, "  First run: EfficientNet-B5 weights download from HuggingFace (~300MB)."))
    log_backend(c(DIM, "  Subsequent starts are much faster (weights cached locally)."))
    start = time.time()
    last_dot = start

    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
                if resp.status == 200:
                    elapsed = time.time() - start
                    log_backend(
                        c(GREEN, f"Backend ready in {elapsed:.1f}s")
                    )
                    return True
        except (urllib.error.URLError, OSError):
            pass

        # Print a dot every 3 seconds to show we're waiting
        now = time.time()
        if now - last_dot >= 3:
            elapsed = now - start
            print(f"  {c(DIM, '...')} waiting for backend ({elapsed:.0f}s)...", flush=True)
            last_dot = now
        time.sleep(1)

    log_error(f"Backend did not become ready within {timeout} seconds.")
    log_error("Check the backend logs above for errors.")
    return False


def wait_for_frontend(timeout: int = FRONTEND_TIMEOUT) -> bool:
    """Poll localhost:3000 until the frontend responds or timeout."""
    log_frontend(f"Waiting for frontend to become ready (up to {timeout}s)...")
    start = time.time()
    last_dot = start

    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"http://localhost:{FRONTEND_PORT}", timeout=3) as resp:
                if resp.status == 200:
                    elapsed = time.time() - start
                    log_frontend(
                        c(GREEN, f"Frontend ready in {elapsed:.1f}s ✓")
                    )
                    return True
        except (urllib.error.URLError, OSError):
            pass

        now = time.time()
        if now - last_dot >= 5:
            print(f"  {c(DIM, '...')} waiting for frontend (Next.js compilation)...", flush=True)
            last_dot = now
        time.sleep(1)

    log_error(f"Frontend did not become ready within {timeout} seconds.")
    return False

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

_processes: list[subprocess.Popen] = []


def shutdown(sig=None, frame=None):
    """Gracefully terminate all child processes."""
    print()
    log_launcher(c(YELLOW, "Shutting down MediaTruth dev servers..."))
    for proc in _processes:
        if proc and proc.poll() is None:
            try:
                if IS_WIN:
                    proc.terminate()
                else:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    log_launcher(c(GREEN, "All processes stopped. Goodbye!"))
    sys.exit(0)

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    banner()

    # ── Pre-flight checks ──────────────────────────────────────────────────
    log_launcher("Running pre-flight checks...")
    print()

    if not check_node():
        sys.exit(1)

    venv, uvicorn = check_backend_env()
    if not uvicorn:
        sys.exit(1)

    if not check_backend_env_file():
        sys.exit(1)

    check_frontend_env_file()

    if not ensure_node_modules():
        sys.exit(1)

    print()
    log_launcher("All pre-flight checks passed. Starting services...")
    print()

    # ── Register signal handler for clean shutdown ─────────────────────────
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Launch backend ─────────────────────────────────────────────────────
    backend_proc = start_backend(uvicorn)
    if not backend_proc:
        sys.exit(1)
    _processes.append(backend_proc)

    # Wait for backend to be healthy
    if not wait_for_backend():
        log_error("Backend startup failed. Shutting down.")
        shutdown()

    print()

    # ── Launch frontend ────────────────────────────────────────────────────
    frontend_proc = start_frontend()
    if not frontend_proc:
        shutdown()
    _processes.append(frontend_proc)

    # Wait for frontend to serve requests
    if not wait_for_frontend():
        log_warn("Frontend may still be compiling. Attempting to open browser anyway...")

    print()

    # ── Open browser ───────────────────────────────────────────────────────
    log_launcher(c(GREEN + BOLD, f"MediaTruth is running!"))
    print()
    print(f"  {c(CYAN + BOLD, '→ Frontend:')}  {c(WHITE, FRONTEND_URL)}")
    print(f"  {c(CYAN + BOLD, '→ Backend:')}   {c(WHITE, BACKEND_URL)}")
    print(f"  {c(CYAN + BOLD, '→ API Docs:')}  {c(WHITE, BACKEND_URL + '/docs')}")
    print()
    print(f"  {c(DIM, 'Press Ctrl+C to stop both servers.')}")
    print()

    try:
        time.sleep(1.5)
        webbrowser.open(FRONTEND_URL)
        log_launcher("Browser opened. Enjoy MediaTruth! 🚀")
    except Exception:
        log_warn("Could not auto-open browser. Navigate to: " + FRONTEND_URL)

    print()

    # ── Keep alive — stream health info until killed ───────────────────────
    try:
        while True:
            # Check if either process died unexpectedly
            be_alive = backend_proc.poll() is None
            fe_alive = frontend_proc.poll() is None

            if not be_alive:
                log_error(
                    f"Backend process exited unexpectedly (code {backend_proc.returncode}). "
                    "Check logs above. Shutting down."
                )
                shutdown()

            if not fe_alive:
                log_error(
                    f"Frontend process exited unexpectedly (code {frontend_proc.returncode}). "
                    "Check logs above. Shutting down."
                )
                shutdown()

            time.sleep(5)

    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
