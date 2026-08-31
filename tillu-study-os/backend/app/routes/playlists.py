"""Playlist REST API routes.

Endpoints
---------
GET  /playlists?subject_id=<uuid>  — list playlists for a subject
POST /playlists/{id}/open          — open playlist in Chromium (Playwright required)
PATCH /playlists/{id}/watch        — mark playlist as watched (Playwright required)

The ``/open`` and ``/watch`` endpoints return HTTP 503 when
``PLAYWRIGHT_ENABLED`` is ``false`` (the default).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["playlists"])

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _playwright_guard() -> None:
    """Raise HTTP 503 when Playwright is disabled."""
    if not settings.playwright_enabled:
        raise HTTPException(
            status_code=503,
            detail="Playwright is not enabled. Set PLAYWRIGHT_ENABLED=true in .env "
                   "and run 'playwright install chromium'.",
        )


# ---------------------------------------------------------------------------
# GET /playlists
# ---------------------------------------------------------------------------

@router.get("")
async def list_playlists(subject_id: UUID = Query(..., description="Subject UUID")):
    """Return all playlists for the given subject.

    Always available regardless of ``PLAYWRIGHT_ENABLED``.
    """
    db = get_client()
    result = (
        db.table("playlists")
        .select("*")
        .eq("subject_id", str(subject_id))
        .execute()
    )
    return result.data


# ---------------------------------------------------------------------------
# POST /playlists/{id}/open
# ---------------------------------------------------------------------------

@router.post("/{playlist_id}/open", status_code=200)
async def open_playlist(playlist_id: UUID):
    """Open the playlist URL in a Chromium browser window.

    Requires ``PLAYWRIGHT_ENABLED=true``.  Returns HTTP 503 when disabled.
    """
    _playwright_guard()

    db = get_client()
    result = (
        db.table("playlists")
        .select("id, url, title")
        .eq("id", str(playlist_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Playlist not found.")

    playlist = result.data[0]
    url: str = playlist["url"]

    try:
        from app.browser.youtube_player import open_playlist as _open
        await _open(url)
    except RuntimeError as exc:
        # Playwright disabled or package missing — shouldn't reach here after
        # _playwright_guard(), but handle defensively.
        logger.error("Failed to open playlist %s: %s", playlist_id, exc)
        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )
    except Exception as exc:
        logger.exception("Unexpected error opening playlist %s", playlist_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("Opened playlist '%s' (%s)", playlist.get("title"), url)
    return {"status": "opened", "playlist_id": str(playlist_id), "url": url}


# ---------------------------------------------------------------------------
# PATCH /playlists/{id}/watch
# ---------------------------------------------------------------------------

@router.patch("/{playlist_id}/watch", status_code=200)
async def mark_playlist_watched(playlist_id: UUID):
    """Mark a playlist as ``watched`` in the database.

    Requires ``PLAYWRIGHT_ENABLED=true``.  Returns HTTP 503 when disabled.

    This endpoint is intentionally gated behind Playwright as per the design
    spec — it is intended to be called from the dashboard after the student
    confirms they have finished watching a playlist opened via ``/open``.
    """
    _playwright_guard()

    db = get_client()

    # Verify the playlist exists first.
    check = (
        db.table("playlists")
        .select("id, watch_status")
        .eq("id", str(playlist_id))
        .execute()
    )
    if not check.data:
        raise HTTPException(status_code=404, detail="Playlist not found.")

    result = (
        db.table("playlists")
        .update({"watch_status": "watched"})
        .eq("id", str(playlist_id))
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500, detail="Failed to update playlist watch status."
        )

    updated = result.data[0]
    logger.info("Playlist %s marked as watched.", playlist_id)
    return {
        "id": updated["id"],
        "watch_status": updated["watch_status"],
    }
