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
# Routes
# ---------------------------------------------------------------------------

app.include_router(tasks.router, prefix="/tasks")
app.include_router(dashboard.router, prefix="/dashboard")
app.include_router(chat.router, prefix="/chat")


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
