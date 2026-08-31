"""Chapter and subject routes.

Endpoints
---------
GET  /chapters               — list all chapters, optionally filtered by subject_id.
                               Ordered by board_weightage desc.
PATCH /chapters/{id}/complete — mark a chapter as completed and zero its weakness_score.
GET  /subjects               — list all subjects (for frontend dropdowns).

Requirements: 13.3, 13.4
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.db import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chapters"])

# Separate router for /subjects so it can be mounted at the top level in main.py.
subjects_router = APIRouter(tags=["subjects"])


# ---------------------------------------------------------------------------
# GET /chapters
# ---------------------------------------------------------------------------

@router.get("/")
async def list_chapters(
    subject_id: Optional[str] = Query(default=None, description="Filter by subject UUID"),
):
    """Return chapters with completion status and weakness score.

    If *subject_id* is provided only chapters belonging to that subject are
    returned.  Results are ordered by ``board_weightage`` descending so the
    highest-weighted chapters appear first.
    """
    db = get_client()

    query = db.table("chapters").select("*, subjects(name)")

    if subject_id:
        query = query.eq("subject_id", subject_id)

    result = query.order("board_weightage", desc=True).execute()
    return result.data


# ---------------------------------------------------------------------------
# PATCH /chapters/{chapter_id}/complete
# ---------------------------------------------------------------------------

@router.patch("/{chapter_id}/complete")
async def complete_chapter(chapter_id: str):
    """Mark a chapter as completed and zero its weakness_score.

    Setting ``weakness_score = 0.0`` means the chapter contributes nothing to
    the Priority Score weakness factor in subsequent plan computations.
    The actual priority-score recomputation for any linked ``study_tasks``
    happens in the planner agent — this endpoint only persists the chapter
    state change.
    """
    db = get_client()

    # Verify the chapter exists before updating.
    existing = (
        db.table("chapters")
        .select("id, name")
        .eq("id", chapter_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail=f"Chapter '{chapter_id}' not found.")

    result = (
        db.table("chapters")
        .update({"is_completed": True, "weakness_score": 0.0})
        .eq("id", chapter_id)
        .execute()
    )

    updated = result.data[0] if result.data else None
    if not updated:
        raise HTTPException(
            status_code=500,
            detail="Chapter update returned no data — check database permissions.",
        )

    logger.info(
        "Chapter '%s' (%s) marked complete. "
        "Priority-score recompute will occur during next planner run.",
        updated.get("name", chapter_id),
        chapter_id,
    )

    return updated


# ---------------------------------------------------------------------------
# GET /subjects  (mounted at /subjects in main.py)
# ---------------------------------------------------------------------------

@subjects_router.get("/")
async def list_subjects():
    """Return all subjects ordered alphabetically.

    Used by frontend dropdowns (mistake form, test score form, etc.).
    """
    db = get_client()
    result = db.table("subjects").select("*").order("name").execute()
    return result.data
