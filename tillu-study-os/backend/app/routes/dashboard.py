"""Dashboard routes — placeholder implementation.

Full dashboard aggregation endpoints will be added in a later task.
"""

from fastapi import APIRouter

router = APIRouter(tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary():
    """Return a high-level study summary for the dashboard."""
    # TODO: implement in later task
    return {}
