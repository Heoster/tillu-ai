"""Mistake tracking routes — POST /mistakes and GET /mistakes.

Implements Requirements 11.2 and 11.3:
  - POST /mistakes: upsert logic (check-then-update or insert) with
    recurrence_count increment on duplicate (profile_id, subject_id,
    chapter_id, description).
  - GET /mistakes: returns all mistakes sorted by recurrence_count desc,
    with optional filtering by subject_id and/or chapter_id.

Also exports ``store_mistake()`` as a standalone async-friendly function
for use by the planner agent.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mistakes"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class MistakeIn(BaseModel):
    profile_id: Optional[str] = None
    subject_id: str
    chapter_id: str
    description: str


# ---------------------------------------------------------------------------
# Shared business logic (reusable by planner agent)
# ---------------------------------------------------------------------------


async def store_mistake(
    subject_id: str,
    chapter_id: str,
    description: str,
    profile_id: Optional[str] = None,
) -> dict:
    """Upsert a mistake record.

    - If a row already exists with the same (profile_id, subject_id,
      chapter_id, description), its ``recurrence_count`` is incremented
      by 1 and the updated row is returned.
    - Otherwise a new row is inserted with ``recurrence_count=1`` and
      the inserted row is returned.

    This function performs synchronous supabase-py calls directly; it is
    named ``async`` so callers can ``await`` it in async contexts without
    changes if a true async supabase client is introduced later.
    """
    db = get_client()

    # Build the existence query; handle NULL profile_id carefully.
    query = (
        db.table("mistakes")
        .select("id, recurrence_count")
        .eq("subject_id", subject_id)
        .eq("chapter_id", chapter_id)
        .eq("description", description)
    )
    if profile_id is not None:
        query = query.eq("profile_id", profile_id)
    else:
        query = query.is_("profile_id", "null")

    existing = query.execute().data

    if existing:
        row = existing[0]
        new_count = row["recurrence_count"] + 1
        updated = (
            db.table("mistakes")
            .update({"recurrence_count": new_count})
            .eq("id", row["id"])
            .execute()
        )
        result_row = updated.data[0] if updated.data else {**row, "recurrence_count": new_count}
        logger.debug(
            "Incremented mistake %s to recurrence_count=%d", row["id"], new_count
        )
        return result_row

    insert_payload: dict = {
        "subject_id": subject_id,
        "chapter_id": chapter_id,
        "description": description,
        "recurrence_count": 1,
    }
    if profile_id is not None:
        insert_payload["profile_id"] = profile_id

    inserted = db.table("mistakes").insert(insert_payload).execute()
    if not inserted.data:
        raise RuntimeError("Insert into mistakes returned no data.")
    logger.debug("Created new mistake row: %s", inserted.data[0].get("id"))
    return inserted.data[0]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", status_code=200)
async def create_mistake(body: MistakeIn):
    """Upsert a mistake.

    If an identical (profile_id, subject_id, chapter_id, description)
    already exists, its recurrence_count is incremented by 1.
    Otherwise a new row is created with recurrence_count=1.

    Returns the created or updated row.
    """
    try:
        row = await store_mistake(
            subject_id=body.subject_id,
            chapter_id=body.chapter_id,
            description=body.description,
            profile_id=body.profile_id,
        )
    except Exception as exc:
        logger.error("Failed to store mistake: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not store mistake: {exc}") from exc

    return row


@router.get("")
async def list_mistakes(
    subject_id: Optional[str] = Query(default=None, description="Filter by subject UUID"),
    chapter_id: Optional[str] = Query(default=None, description="Filter by chapter UUID"),
):
    """Return all mistake records sorted by recurrence_count descending.

    Accepts optional ``subject_id`` and ``chapter_id`` query parameters to
    narrow results. The response is a flat list; the caller may group by
    subject/chapter on the frontend.
    """
    db = get_client()

    query = db.table("mistakes").select("*").order("recurrence_count", desc=True)

    if subject_id is not None:
        query = query.eq("subject_id", subject_id)
    if chapter_id is not None:
        query = query.eq("chapter_id", chapter_id)

    try:
        result = query.execute()
    except Exception as exc:
        logger.error("Failed to fetch mistakes: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not fetch mistakes: {exc}") from exc

    return result.data
