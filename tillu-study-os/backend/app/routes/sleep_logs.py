"""Sleep log routes — POST /sleep-logs and GET /sleep-logs.

Implements Requirements 10.2 and 10.3:
  - Validates that sleep_end is after sleep_start (with overnight crossing support).
  - Computes and stores total_sleep_hours rounded to 2 decimal places.
  - Exposes validate_sleep_log() as a standalone helper importable by sleep_agent.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sleep-logs"])


# ---------------------------------------------------------------------------
# Validation helper (also importable by sleep_agent)
# ---------------------------------------------------------------------------

def validate_sleep_log(sleep_start: str, sleep_end: str) -> float:
    """Parse HH:MM strings and return total_sleep_hours as a float.

    Handles overnight sleep: when sleep_end <= sleep_start time-wise,
    one day is added to the end datetime before computing the duration.

    Raises:
        HTTPException(400): if the computed duration is <= 0 hours.

    Returns:
        total_sleep_hours (float): duration in hours, rounded to 2 decimal places.
    """
    fmt = "%H:%M"
    start_dt = datetime.strptime(sleep_start, fmt)
    end_dt = datetime.strptime(sleep_end, fmt)

    # Handle overnight crossing (e.g. 23:00 → 06:00 the next day)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    total_sleep_hours = (end_dt - start_dt).total_seconds() / 3600.0

    if total_sleep_hours <= 0:
        raise HTTPException(
            status_code=400,
            detail="sleep_end must be after sleep_start",
        )

    return round(total_sleep_hours, 2)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SleepLogCreate(BaseModel):
    profile_id: Optional[str] = Field(None, description="UUID of the profile (optional)")
    log_date: Optional[str] = Field(
        None,
        description="Date in YYYY-MM-DD format; defaults to today if omitted",
    )
    sleep_start: str = Field(..., description="Sleep start time in HH:MM format")
    sleep_end: str = Field(..., description="Sleep end time in HH:MM format")
    notes: Optional[str] = Field(None, description="Optional free-text notes")


# ---------------------------------------------------------------------------
# POST /sleep-logs
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_sleep_log(body: SleepLogCreate):
    """Store a new sleep log entry after validating the sleep window.

    Validates:
    - sleep_end is after sleep_start (overnight crossing handled automatically).
    - total_sleep_hours > 0.

    Returns the created row from Supabase.
    """
    total_sleep_hours = validate_sleep_log(body.sleep_start, body.sleep_end)

    log_date = body.log_date or str(date.today())

    record: dict = {
        "log_date": log_date,
        "sleep_start": body.sleep_start,
        "sleep_end": body.sleep_end,
        "total_sleep_hours": total_sleep_hours,
    }
    if body.profile_id is not None:
        record["profile_id"] = body.profile_id
    if body.notes is not None:
        record["notes"] = body.notes

    db = get_client()
    result = db.table("sleep_logs").insert(record).execute()

    if not result.data:
        logger.error("Supabase insert returned no data for sleep_log: %s", record)
        raise HTTPException(status_code=500, detail="Failed to create sleep log entry.")

    logger.info("Sleep log created: %s", result.data[0])
    return result.data[0]


# ---------------------------------------------------------------------------
# GET /sleep-logs
# ---------------------------------------------------------------------------

@router.get("")
async def list_sleep_logs(
    profile_id: Optional[str] = Query(None, description="Filter by profile UUID"),
):
    """Return the most recent 30 sleep log entries, optionally filtered by profile_id."""
    db = get_client()

    query = (
        db.table("sleep_logs")
        .select("*")
        .order("created_at", desc=True)
        .limit(30)
    )

    if profile_id is not None:
        query = query.eq("profile_id", profile_id)

    result = query.execute()
    return result.data
