"""Task CRUD and study session endpoints.

Routes (all mounted under the ``/tasks`` prefix in ``main.py``):
  GET   /tasks/today                    — today's tasks sorted by priority_score desc
  GET   /tasks/sessions/today           — all sessions started today
  PATCH /tasks/{task_id}/status         — update status, broadcast WS event
  POST  /tasks/{task_id}/session/start  — open a study session
  POST  /tasks/{task_id}/session/stop   — close session, accumulate actual_duration_min

NOTE: ``/tasks/sessions/today`` is registered BEFORE any ``/{task_id}/…`` routes so
FastAPI does not swallow the literal path segment ``sessions`` as a task_id parameter.

Requirements: 4.1, 5.2, 5.3, 15.2, 15.3, 15.4, 15.5
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from math import ceil
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_client
from app.services.task_service import update_task
from app.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])

# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

TaskStatus = Literal["pending", "in-progress", "completed", "missed"]


class StatusUpdate(BaseModel):
    status: TaskStatus


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _accumulate_actual_duration(task_id: str) -> None:
    """Sum all *completed* session ``duration_min`` values for the task and
    write the total to ``study_tasks.actual_duration_min``.

    Implements Requirement 15.4: actual_duration_min reflects the sum of all
    completed session durations.
    """
    db = get_client()
    sessions_result = (
        db.table("study_sessions")
        .select("duration_min")
        .eq("task_id", task_id)
        .eq("status", "completed")
        .execute()
    )
    total = sum((row["duration_min"] or 0) for row in sessions_result.data)
    db.table("study_tasks").update({"actual_duration_min": total}).eq("id", task_id).execute()


# ---------------------------------------------------------------------------
# GET /tasks/today
# ---------------------------------------------------------------------------


@router.get("/today", summary="Today's tasks sorted by priority_score desc")
async def get_today_tasks() -> list:
    """Return every study task scheduled for today, ordered by priority score.

    Joins chapter and subject names so the frontend can display them without
    extra round-trips.  Satisfies Requirement 4.1 / 5.5.
    """
    try:
        result = (
            get_client()
            .table("study_tasks")
            .select("*, chapters(name), subjects(name)")
            .eq("scheduled_date", str(date.today()))
            .order("priority_score", desc=True)
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.error("Failed to fetch today's tasks: %s", exc)
        raise HTTPException(status_code=500, detail="Could not fetch today's tasks.")


# ---------------------------------------------------------------------------
# GET /tasks/sessions/today
# IMPORTANT: must be declared before /{task_id}/… routes to avoid being
# captured by the path-parameter matcher.
# ---------------------------------------------------------------------------


@router.get("/sessions/today", summary="All study sessions started today")
async def get_today_sessions() -> list:
    """Return every ``study_sessions`` row whose ``started_at`` falls on today's date.

    Satisfies Requirement 15.5.
    """
    try:
        today_start = f"{date.today()}T00:00:00"
        today_end = f"{date.today()}T23:59:59"
        result = (
            get_client()
            .table("study_sessions")
            .select("*")
            .gte("started_at", today_start)
            .lte("started_at", today_end)
            .order("started_at", desc=False)
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.error("Failed to fetch today's sessions: %s", exc)
        raise HTTPException(status_code=500, detail="Could not fetch today's sessions.")


# ---------------------------------------------------------------------------
# PATCH /tasks/{task_id}/status
# ---------------------------------------------------------------------------


@router.patch("/{task_id}/status", summary="Update task status and broadcast WebSocket event")
async def update_task_status(task_id: str, body: StatusUpdate) -> dict:
    """Update a task's status.

    Delegates to the task service layer (``update_task``) so that
    ``priority_score`` is recomputed whenever a factor field changes.
    Broadcasts a ``task_update`` WS event to all connected frontend clients.

    Satisfies Requirements 5.2, 5.3, 4.6.
    """
    try:
        updated = update_task(task_id, {"status": body.status})
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Broadcast — non-fatal; a WS failure must not break the REST response.
    try:
        await ws_manager.broadcast(
            {
                "type": "task_update",
                "task_id": task_id,
                "status": body.status,
            }
        )
    except Exception as exc:
        logger.warning("WebSocket broadcast failed after status update: %s", exc)

    return updated


# ---------------------------------------------------------------------------
# POST /tasks/{task_id}/session/start
# ---------------------------------------------------------------------------


@router.post("/{task_id}/session/start", summary="Start a study session for a task")
async def start_session(task_id: str) -> dict:
    """Create a ``study_sessions`` row with ``status='active'`` for the task.

    Returns the newly created session record.  Satisfies Requirement 15.2.
    """
    db = get_client()
    started_at = datetime.utcnow().isoformat()

    try:
        result = (
            db.table("study_sessions")
            .insert(
                {
                    "task_id": task_id,
                    "started_at": started_at,
                    "status": "active",
                }
            )
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to create study session for task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail="Could not start study session.")

    if not result.data:
        raise HTTPException(status_code=500, detail="Session insert returned no data.")

    return result.data[0]


# ---------------------------------------------------------------------------
# POST /tasks/{task_id}/session/stop
# ---------------------------------------------------------------------------


@router.post("/{task_id}/session/stop", summary="Stop the active study session for a task")
async def stop_session(task_id: str) -> dict:
    """Close the active session for the task.

    Steps:
    1. Find the most recent ``active`` session for ``task_id``.
    2. Compute ``duration_min = ceil((ended_at - started_at).total_seconds() / 60)``.
    3. Update the session row with ``ended_at``, ``duration_min``, ``status='completed'``.
    4. Accumulate total completed session minutes → ``study_tasks.actual_duration_min``.

    Returns the updated session record.  Satisfies Requirements 15.3, 15.4.
    """
    db = get_client()

    # Find the most-recently-started active session for this task
    fetch_result = (
        db.table("study_sessions")
        .select("*")
        .eq("task_id", task_id)
        .eq("status", "active")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )

    if not fetch_result.data:
        raise HTTPException(
            status_code=404,
            detail=f"No active session found for task {task_id!r}.",
        )

    session = fetch_result.data[0]
    session_id = session["id"]

    # Parse started_at — Supabase returns ISO 8601 strings (may include timezone)
    started_at_raw: str = session["started_at"]
    try:
        # Replace trailing 'Z' with '+00:00' for fromisoformat compatibility
        started_at_dt = datetime.fromisoformat(started_at_raw.replace("Z", "+00:00"))
        # Work in naive UTC throughout
        if started_at_dt.tzinfo is not None:
            started_at_naive = started_at_dt.replace(tzinfo=None)
        else:
            started_at_naive = started_at_dt
    except ValueError:
        logger.error("Could not parse started_at %r for session %s", started_at_raw, session_id)
        raise HTTPException(status_code=500, detail="Could not parse session start time.")

    ended_at = datetime.utcnow()
    delta_seconds = (ended_at - started_at_naive).total_seconds()
    # Ensure at least 1 minute so duration_min is never 0
    duration_min = max(1, ceil(delta_seconds / 60))

    ended_at_iso = ended_at.isoformat()

    # Persist the closed session
    try:
        update_result = (
            db.table("study_sessions")
            .update(
                {
                    "ended_at": ended_at_iso,
                    "duration_min": duration_min,
                    "status": "completed",
                }
            )
            .eq("id", session_id)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to close session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail="Could not stop study session.")

    if not update_result.data:
        raise HTTPException(status_code=500, detail="Session update returned no data.")

    # Accumulate actual_duration_min on the parent task (non-fatal)
    try:
        _accumulate_actual_duration(task_id)
    except Exception as exc:
        logger.warning(
            "Could not update actual_duration_min for task %s: %s", task_id, exc
        )

    return update_result.data[0]
