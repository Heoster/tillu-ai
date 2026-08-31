"""FastAPI application entry point for Tillu AI Study OS.

Startup sequence (lifespan):
  1. Probe Supabase connectivity — abort if unreachable.
  2. Start APScheduler background jobs.

Shutdown sequence:
  1. Stop APScheduler gracefully.

Middleware:
  - CORS restricted to settings.frontend_origin.

Global exception handler:
  - Any unhandled Exception → HTTP 500 JSON + full traceback logged.
"""

import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import verify_connection
from app.scheduler import start_scheduler, stop_scheduler
from app.websocket_manager import ws_manager
from app.routes import tasks, dashboard, chat

# Optional routes — created by later tasks.  Import failures are silenced so
# the app stays runnable while those files are still stubs / not yet created.
try:
    from app.routes import chapters as chapters_router
except ImportError:
    chapters_router = None  # type: ignore[assignment]

try:
    from app.routes.chapters import subjects_router
except ImportError:
    subjects_router = None  # type: ignore[assignment]

try:
    from app.routes import sleep_logs as sleep_logs_router
except ImportError:
    sleep_logs_router = None  # type: ignore[assignment]

try:
    from app.routes import mistakes as mistakes_router
except ImportError:
    mistakes_router = None  # type: ignore[assignment]

try:
    from app.routes import tests as tests_router
except ImportError:
    tests_router = None  # type: ignore[assignment]

try:
    from app.routes import reminders as reminders_router
except ImportError:
    reminders_router = None  # type: ignore[assignment]

try:
    from app.routes import playlists as playlists_router
except ImportError:
    playlists_router = None  # type: ignore[assignment]

try:
    from app.routes import voice as voice_router
except ImportError:
    voice_router = None  # type: ignore[assignment]

try:
    from app.routes import rag as rag_router
except ImportError:
    rag_router = None  # type: ignore[assignment]

try:
    from app.routes import documents as documents_router
except ImportError:
    documents_router = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup → yield → shutdown lifecycle hook."""
    # --- Startup ---
    logger.info("Starting Tillu AI Study OS backend…")
    await verify_connection()
    logger.info("Database connection verified.")
    await start_scheduler()

    yield  # Application runs here

    # --- Shutdown ---
    await stop_scheduler()
    logger.info("Tillu AI Study OS backend shut down.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Tillu AI Study OS",
    description="AI-powered CBSE Class 12 study companion backend.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler: logs the full traceback and returns HTTP 500 JSON."""
    logger.error(
        "Unhandled exception on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


# ---------------------------------------------------------------------------
# Routes — always-present
# ---------------------------------------------------------------------------

app.include_router(tasks.router, prefix="/tasks")
app.include_router(dashboard.router, prefix="/dashboard")
app.include_router(chat.router, prefix="/chat")

# ---------------------------------------------------------------------------
# Routes — optional (registered only when the module file exists)
# ---------------------------------------------------------------------------

if chapters_router is not None:
    app.include_router(chapters_router.router, prefix="/chapters")

if subjects_router is not None:
    app.include_router(subjects_router, prefix="/subjects")

if sleep_logs_router is not None:
    app.include_router(sleep_logs_router.router, prefix="/sleep-logs")

if mistakes_router is not None:
    app.include_router(mistakes_router.router, prefix="/mistakes")

if tests_router is not None:
    app.include_router(tests_router.router, prefix="/tests")

if reminders_router is not None:
    app.include_router(reminders_router.router, prefix="/reminders")

if playlists_router is not None:
    app.include_router(playlists_router.router, prefix="/playlists")

if voice_router is not None:
    app.include_router(voice_router.router, prefix="/voice")

if rag_router is not None:
    app.include_router(rag_router.router, prefix="/rag")

if documents_router is not None:
    app.include_router(documents_router.router, prefix="/documents")


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe used by the launcher and load balancer."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Live update stream for dashboard task cards and notifications."""
    await ws_manager.connect(websocket)
