"""Sleep window agent for Tillu AI Study OS.

Provides get_sleep_window() — used by the nightly planner to determine
when the student is sleeping so no tasks are scheduled during that window.

Implements Requirements 10.4 and 10.5.
"""

import logging
from datetime import date, datetime, timedelta

from app.config import settings
from app.db import get_client

logger = logging.getLogger(__name__)


async def get_sleep_window() -> tuple[str, str]:
    """Return (sleep_start, sleep_end) as HH:MM strings for today.

    Queries sleep_logs for today's entry (most recent if multiple).
    Falls back to settings.default_sleep_start / default_sleep_end if no entry
    exists, and logs a WARNING that defaults were applied.

    Returns:
        Tuple (sleep_start, sleep_end) as HH:MM strings e.g. ("23:00", "06:00").
    """
    db = get_client()
    result = (
        db.table("sleep_logs")
        .select("sleep_start, sleep_end")
        .eq("log_date", str(date.today()))
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        row = result.data[0]
        # Supabase may return TIME columns as "HH:MM:SS" strings; normalise to "HH:MM"
        sleep_start = _normalise_time(str(row["sleep_start"]))
        sleep_end = _normalise_time(str(row["sleep_end"]))
        return sleep_start, sleep_end

    logger.warning(
        "No sleep log found for %s — using default window %s–%s",
        date.today(),
        settings.default_sleep_start,
        settings.default_sleep_end,
    )
    return settings.default_sleep_start, settings.default_sleep_end


def _normalise_time(value: str) -> str:
    """Ensure a time string is in HH:MM format.

    Postgres TIME columns are sometimes returned as "HH:MM:SS".
    Strips the seconds component if present.
    """
    parts = value.strip().split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return value


def sleep_window_overlaps(
    task_start: str,
    task_end: str,
    sleep_start: str,
    sleep_end: str,
) -> bool:
    """Return True if a task time block overlaps with the sleep window.

    Both the task block and sleep window are given as HH:MM strings.
    Overnight crossings (e.g. sleep 23:00–06:00, or a task spanning midnight)
    are handled correctly.

    The algorithm anchors all times to a common base day then applies a
    two-pass check:

    Pass 1 — task on base day vs sleep window
        If the sleep window crosses midnight it is extended by +1 day.
        If the task ends before or at its start it is extended by +1 day.
        Standard overlap test: ts < se and te > ss.

    Pass 2 — task shifted one day forward vs sleep window (same base)
        This covers early-morning tasks (e.g. 01:00–03:00) that conceptually
        fall *after* a midnight-crossing sleep window (e.g. 23:00–06:00 next
        day).  Adding one day to the task brings it into the same numeric
        range as the extended sleep window, making the standard overlap test
        work correctly.

    Two intervals [A, B) and [C, D) overlap iff A < D and B > C.
    """
    fmt = "%H:%M"

    ts = datetime.strptime(task_start, fmt)
    te = datetime.strptime(task_end, fmt)
    ss = datetime.strptime(sleep_start, fmt)
    se = datetime.strptime(sleep_end, fmt)

    # Handle overnight crossing for sleep window
    sleep_crosses_midnight = se <= ss
    if sleep_crosses_midnight:
        se += timedelta(days=1)

    # Handle overnight crossing for task window
    if te <= ts:
        te += timedelta(days=1)

    # Pass 1: task at base-day position
    if ts < se and te > ss:
        return True

    # Pass 2: only needed when sleep crosses midnight — shift task forward by
    # one day so early-morning tasks (e.g. 01:00) are compared correctly
    # against the extended sleep window (e.g. 23:00 → 30:00).
    if sleep_crosses_midnight:
        ts2 = ts + timedelta(days=1)
        te2 = te + timedelta(days=1)
        if ts2 < se and te2 > ss:
            return True

    return False
