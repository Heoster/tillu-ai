"""Reminder agent — checks due reminders and dispatches three-channel notifications.

Channels:
  1. Windows toast notification (plyer)
  2. Audio chime (pygame)
  3. WebSocket broadcast event to connected frontend clients

Each channel failure is caught independently — if one fails the others still fire.
After dispatch, reminder status is updated to 'fired' (monotone: pending → fired only).

Implements Requirements: 8.1, 8.2, 8.7, 14.3, 14.4
"""
import logging
import os
from datetime import datetime, timedelta

from app.db import get_client
from app.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


async def check_reminders() -> None:
    """Query reminders due in the next 5 minutes and dispatch notifications.

    Only reminders with status='pending' whose scheduled_at falls within
    [now, now + 5 minutes] are selected.  Each matched reminder is dispatched
    via all three notification channels then marked 'fired'.
    """
    db = get_client()
    now = datetime.utcnow()
    window_end = now + timedelta(minutes=5)

    result = (
        db.table("reminders")
        .select("*")
        .eq("status", "pending")
        .gte("scheduled_at", now.isoformat())
        .lte("scheduled_at", window_end.isoformat())
        .execute()
    )

    for reminder in result.data:
        await _dispatch_reminder(db, reminder)


async def _dispatch_reminder(db, reminder: dict) -> None:
    """Dispatch all three notification channels for a reminder, then mark it fired.

    Each channel failure is caught independently so the remaining channels
    still execute regardless of any individual channel's failure.
    After all channels are attempted, the reminder status is updated to
    'fired' (pending → fired transition only — never backward).
    """
    # Channel 1: Windows toast (non-fatal)
    _send_toast(reminder["title"], reminder.get("scheduled_at", ""))

    # Channel 2: Audio chime (non-fatal)
    _play_chime()

    # Channel 3: WebSocket broadcast (non-fatal)
    try:
        await ws_manager.broadcast({
            "type": "reminder",
            "reminder_id": reminder["id"],
            "title": reminder["title"],
            "scheduled_at": reminder.get("scheduled_at", ""),
        })
    except Exception as exc:
        logger.warning(
            "WebSocket broadcast failed for reminder %s: %s", reminder["id"], exc
        )

    # Mark fired — status only transitions pending → fired, never backward
    try:
        (
            db.table("reminders")
            .update({"status": "fired"})
            .eq("id", reminder["id"])
            .execute()
        )
        logger.info("Reminder %s fired: %s", reminder["id"], reminder["title"])
    except Exception as exc:
        logger.error(
            "Failed to mark reminder %s as fired: %s", reminder["id"], exc
        )


def _send_toast(title: str, scheduled_at: str) -> None:
    """Send a Windows toast notification. Logs error on failure, never raises."""
    try:
        from plyer import notification  # type: ignore[import]

        notification.notify(
            title="Tillu Reminder",
            message=f"{title} at {scheduled_at}",
            app_name="Tillu AI Study OS",
            timeout=10,
        )
    except Exception as exc:
        logger.error("Toast notification failed: %s", exc)


def _play_chime() -> None:
    """Play an audio chime. Logs warning on failure, never raises."""
    try:
        import pygame  # type: ignore[import]

        pygame.mixer.init()
        # Look for chime.mp3 relative to the backend root
        chime_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "assets", "chime.mp3"
        )
        if os.path.exists(chime_path):
            pygame.mixer.music.load(chime_path)
            pygame.mixer.music.play()
        else:
            logger.warning(
                "Chime file not found at %s — skipping audio", chime_path
            )
    except Exception as exc:
        logger.warning("Audio chime failed: %s — toast still sent", exc)
