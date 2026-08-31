"""Test score routes.

Endpoints
---------
POST /tests            — store a test score (validates 0 ≤ score ≤ max_score and max_score > 0).
GET  /tests/summary    — per-subject average percentage, sorted by avg_percentage asc (weakest first).
GET  /tests            — all test records, optional ?subject_id= filter.

Requirements: 12.2, 12.3, 12.4
"""

import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tests"])


# ---------------------------------------------------------------------------
# Validation helper (exported for use by other modules)
# ---------------------------------------------------------------------------

def validate_test_score(score: float, max_score: float) -> None:
    """Validate that *score* and *max_score* are within acceptable bounds.

    Raises:
        HTTPException 400 — if ``max_score`` is not > 0, or if ``score`` is
        outside the range ``[0, max_score]``.
    """
    if max_score <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"max_score must be greater than 0. Got {max_score}.",
        )
    if score < 0 or score > max_score:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Score must be between 0 and {max_score}. Got {score}."
            ),
        )


# ---------------------------------------------------------------------------
# Request body model
# ---------------------------------------------------------------------------

class TestScoreCreate(BaseModel):
    profile_id: Optional[str] = None   # UUID string, optional
    subject_id: str                    # UUID string, required
    chapter_id: Optional[str] = None   # UUID string, optional
    score: float
    max_score: float


# ---------------------------------------------------------------------------
# POST /tests
# ---------------------------------------------------------------------------

@router.post("/", status_code=201)
async def create_test_score(body: TestScoreCreate):
    """Store a test score record after validating the score range.

    ``percentage`` is a GENERATED ALWAYS column in Postgres and must **not**
    be included in the INSERT payload — the database computes it automatically
    as ``score / max_score * 100``.
    """
    validate_test_score(body.score, body.max_score)

    db = get_client()

    payload: dict = {
        "subject_id": body.subject_id,
        "score": body.score,
        "max_score": body.max_score,
    }
    if body.profile_id is not None:
        payload["profile_id"] = body.profile_id
    if body.chapter_id is not None:
        payload["chapter_id"] = body.chapter_id

    result = db.table("tests").insert(payload).execute()

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Test score insertion returned no data — check database permissions.",
        )

    inserted = result.data[0]
    logger.info(
        "Test score recorded: subject=%s score=%.2f/%.2f (%.2f%%)",
        body.subject_id,
        body.score,
        body.max_score,
        inserted.get("percentage", 0),
    )
    return inserted


# ---------------------------------------------------------------------------
# GET /tests/summary
# ---------------------------------------------------------------------------

@router.get("/summary")
async def get_tests_summary():
    """Return per-subject average percentage, sorted by avg_percentage asc.

    Supabase REST does not support GROUP BY aggregates natively, so all test
    records are fetched and the average is computed in Python.

    Subjects with the lowest average appear first (weakest subjects first),
    allowing the planner to identify areas that need the most attention.
    """
    db = get_client()

    result = db.table("tests").select("subject_id, percentage").execute()
    all_tests = result.data or []

    # Group percentages by subject_id, ignoring rows where percentage is NULL.
    groups: dict[str, list[float]] = defaultdict(list)
    for row in all_tests:
        if row.get("percentage") is not None:
            groups[row["subject_id"]].append(float(row["percentage"]))

    summary = [
        {
            "subject_id": sid,
            "avg_percentage": round(sum(pcts) / len(pcts), 2),
        }
        for sid, pcts in groups.items()
    ]

    # Weakest subjects first (ascending average).
    summary.sort(key=lambda x: x["avg_percentage"])

    return summary


# ---------------------------------------------------------------------------
# GET /tests
# ---------------------------------------------------------------------------

@router.get("/")
async def list_tests(
    subject_id: Optional[str] = Query(default=None, description="Filter by subject UUID"),
):
    """Return all test records, optionally filtered by subject_id.

    Results are ordered by ``taken_at`` descending (most recent first).
    """
    db = get_client()

    query = db.table("tests").select("*")

    if subject_id:
        query = query.eq("subject_id", subject_id)

    result = query.order("taken_at", desc=True).execute()
    return result.data or []
