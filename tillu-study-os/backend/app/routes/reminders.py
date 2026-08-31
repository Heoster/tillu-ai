"""Reminder management routes — POST /reminders and GET /reminders.

Implements Requirements 14.2 and 14.5:
  - POST /reminders: stores a new reminder with status='pending' in the
    ``reminders`` table; returns the created row with HTTP 201.
  - GET /reminders: returns today's reminders (where the date portion of
    ``scheduled_at`` equals today), ordered by ``scheduled_at`` ascending.
    Optional ``profile_id`` query parameter narrows results to a single profile.

The ``reminders`` table schema (from migration 001_initial_schema.sql):
  id           UUID PK (gen_random_uuid)
  profile_id   UUID FK → profiles.id  (nullable)
  title        TEXT NOT NULL
  scheduled_at TIMESTAMPTZ NOT NULL
  status       TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'fired'))
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reminders"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ReminderIn(BaseModel):
    profile_id: Optional[str] = None
    title: str
    scheduled_at: str  # ISO 8601 datetime string, e.g. "2025-07-25T09:30:00"


# ---------------------------------------------------------------------------
# POST /reminders
# ---------------------------------------------------------------------------


@router.post("", status_code=201, summary="Create a reminder with status=pending")
async def create_reminder(body: ReminderIn) -> dict:
    """Create a new reminder record.

    Stores the reminder in the ``reminders`` table with ``status='pending'``.
    Returns the newly created row.

    Satisfies Requirement 14.2.
    """
    db = get_client()

    payload: dict = {
        "title": body.title,
        "scheduled_at": body.scheduled_at,
        "status": "pending",
    }
    if body.profile_id is not None:
        payload["profile_id"] = body.profile_id

    try:
        result = db.table("reminders").insert(payload).execute()
    except Exception as exc:
        logger.error("Failed to create reminder: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Could not create reminder: {exc}"
        ) from exc

    if not result.data:
        raise HTTPException(status_code=500, detail="Reminder insert returned no data.")

    logger.debug("Created reminder: %s", result.data[0].get("id"))
    return result.data[0]


# ---------------------------------------------------------------------------
# GET /reminders
# ---------------------------------------------------------------------------


@router.get("", summary="Today's reminders with status")
async def list_today_reminders(
    profile_id: Optional[str] = Query(
        default=None, description="Filter by profile UUID"
    ),
) -> list:
    """Return reminders whose ``scheduled_at`` date portion equals today.

    The filter is implemented as a range query:
      scheduled_at >= today 00:00:00  AND  scheduled_at <= today 23:59:59

    Results are ordered by ``scheduled_at`` ascending so the next upcoming
    reminder always appears first.

    Accepts an optional ``profile_id`` query parameter to narrow results to
    a single student profile.

    Satisfies Requirement 14.5.
    """
    db = get_client()
    today = str(date.today())
    day_start = f"{today}T00:00:00"
    day_end = f"{today}T23:59:59"

    query = (
        db.table("reminders")
        .select("*")
        .gte("scheduled_at", day_start)
        .lte("scheduled_at", day_end)
        .order("scheduled_at", desc=False)
    )

    if profile_id is not None:
        query = query.eq("profile_id", profile_id)

    try:
        result = query.execute()
    except Exception as exc:
        logger.error("Failed to fetch today's reminders: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Could not fetch reminders: {exc}"
        ) from exc

    return result.data
