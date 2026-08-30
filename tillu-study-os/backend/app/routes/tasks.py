"""Task routes — placeholder implementation.

Full CRUD and session endpoints will be wired in task 6.3.
"""

from fastapi import APIRouter

router = APIRouter(tags=["tasks"])


@router.get("/today")
async def get_today_tasks():
    """Return today's tasks sorted by priority_score desc."""
    # TODO: implement in task 6.3
    return []
