"""Daily planner agent for Tillu AI Study OS.

run_nightly_plan():  Generates tomorrow's study schedule via Tillu AI,
                     enforces sleep-window constraints, respects the available-
                     hours budget, and writes tasks to study_tasks.

check_missed_tasks(): Marks overdue pending tasks as 'missed' and broadcasts
                      a WebSocket event for each.

Sleep-window enforcement rules:
  - No scheduled task block may overlap the student's sleep window.
  - Total scheduled minutes must not exceed (24*60 - sleep_duration_minutes).

Context enrichment (Requirements 11.4, 12.5):
  - Weakness boost: top-10 mistake chapters receive a proportional weakness
    boost applied to their tasks' weakness_score before planning.
  - Test summary: subjects with below-average test scores receive an
    additional weakness contribution on all tasks for that subject.

Implements Requirements 9.1–9.6, 11.4, 12.5.
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException

from app.agents.sleep_agent import get_sleep_window, sleep_window_overlaps
from app.agents.tillu_brain import ask_tillu
from app.db import get_client
from app.priority import PriorityFactors, clamp, compute_priority_score
from app.routes.sleep_logs import validate_sleep_log
from app.services.task_service import create_task, update_task
from app.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: compute sleep duration
# ---------------------------------------------------------------------------


def _compute_sleep_duration(sleep_start: str, sleep_end: str) -> float:
    """Return sleep duration in hours, falling back to 8.0 on error.

    Uses validate_sleep_log() from the sleep_logs route.  Any HTTPException
    (e.g. invalid window) is caught and the default 8-hour duration is returned.

    Args:
        sleep_start: HH:MM string, e.g. "23:00".
        sleep_end:   HH:MM string, e.g. "06:00".

    Returns:
        Duration in hours as a float; minimum 0.0, maximum 24.0.
    """
    try:
        return validate_sleep_log(sleep_start, sleep_end)
    except HTTPException:
        logger.warning(
            "validate_sleep_log raised HTTPException for window %s–%s — defaulting to 8.0 h",
            sleep_start,
            sleep_end,
        )
        return 8.0


# ---------------------------------------------------------------------------
# Helper: fetch top-mistake chapters
# ---------------------------------------------------------------------------


def _get_top_mistake_chapters(db, limit: int = 10) -> list[dict[str, Any]]:
    """Return the top *limit* chapters by total mistake recurrence count.

    Groups rows in the ``mistakes`` table by ``chapter_id``, sums
    ``recurrence_count``, and returns the top ``limit`` entries sorted by
    total recurrence descending.  Each entry also carries a normalised
    ``weakness_boost`` value in [0.0, 1.0] so that callers can apply a
    proportional weakness penalty to tasks involving those chapters.

    The boost is computed as::

        weakness_boost = chapter_total / max_total_in_set

    where ``max_total_in_set`` is the highest aggregated recurrence count
    among the returned entries.  This guarantees the worst chapter gets a
    boost of 1.0 and all others scale proportionally.

    Returns:
        A list of dicts with keys ``chapter_id``, ``total_recurrence``, and
        ``weakness_boost`` (float in [0.0, 1.0]).
    """
    result = db.table("mistakes").select("chapter_id, recurrence_count").execute()
    rows = result.data or []

    # Aggregate by chapter_id
    totals: dict[str, int] = {}
    for row in rows:
        cid = row.get("chapter_id")
        if cid is None:
            continue
        totals[cid] = totals.get(cid, 0) + int(row.get("recurrence_count", 1))

    sorted_chapters = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    top = sorted_chapters[:limit]

    if not top:
        return []

    max_total = top[0][1]  # highest recurrence count (already sorted desc)

    return [
        {
            "chapter_id": cid,
            "total_recurrence": total,
            # Proportional boost: worst chapter → 1.0, others scale down.
            "weakness_boost": round(total / max_total, 6) if max_total > 0 else 0.0,
        }
        for cid, total in top
    ]


# ---------------------------------------------------------------------------
# Helper: build test-summary weakness map
# ---------------------------------------------------------------------------


def _build_subject_weakness_map(test_summary: list[dict[str, Any]]) -> dict[str, float]:
    """Convert test summary records into a subject → weakness contribution map.

    For each subject the weakness contribution is::

        subject_weakness = 1.0 - (avg_percentage / 100.0)

    A subject scoring 100 % contributes 0.0; one scoring 50 % contributes
    0.5.  The result is clamped to [0.0, 1.0] to handle edge cases.

    Args:
        test_summary: List of dicts with ``subject_id`` and ``avg_percentage``
                      as returned by the ``/tests/summary`` route logic.

    Returns:
        Dict mapping subject_id → weakness_contribution (float in [0.0, 1.0]).
    """
    result: dict[str, float] = {}
    for entry in test_summary:
        sid = entry.get("subject_id")
        avg_pct = entry.get("avg_percentage")
        if sid is None or avg_pct is None:
            continue
        # Lower average → higher weakness contribution
        result[sid] = clamp(1.0 - float(avg_pct) / 100.0)
    return result


# ---------------------------------------------------------------------------
# Helper: enrich task weakness scores
# ---------------------------------------------------------------------------


def _enrich_task_weakness(
    tasks: list[dict[str, Any]],
    top_mistake_chapters: list[dict[str, Any]],
    subject_weakness_map: dict[str, float],
    *,
    mistake_weight: float = 0.3,
    test_weight: float = 0.2,
) -> list[dict[str, Any]]:
    """Return a copy of *tasks* with enriched ``weakness_score`` values.

    Two enrichment signals are blended into each task's ``weakness_score``:

    1. **Mistake boost** (Requirement 11.4):
       Tasks whose ``chapter_id`` appears in the top-10 mistake chapters
       receive a proportional ``weakness_boost`` scaled by ``mistake_weight``
       (default 0.3).

    2. **Test weakness** (Requirement 12.5):
       Tasks whose ``subject_id`` appears in the subject weakness map receive
       an additional contribution scaled by ``test_weight`` (default 0.2).

    The blended formula::

        enriched_weakness = clamp(
            base_weakness
            + mistake_weight * mistake_boost     # 0 if chapter not in top-10
            + test_weight   * subject_weakness   # 0 if no test data for subject
        )

    The original task dicts are **not** mutated; the function returns new
    copies.  The enriched ``weakness_score`` is also used to recompute
    ``priority_score`` in-place on each task copy so callers receive fully
    up-to-date scores.

    Args:
        tasks: Pending study tasks from the DB.
        top_mistake_chapters: Output of ``_get_top_mistake_chapters()``.
        subject_weakness_map: Output of ``_build_subject_weakness_map()``.
        mistake_weight: How much to scale the mistake boost (default 0.3).
        test_weight: How much to scale the subject weakness contribution (default 0.2).

    Returns:
        New list of task dicts with updated ``weakness_score`` and
        ``priority_score`` fields.
    """
    # Fast lookup: chapter_id → weakness_boost
    chapter_boost: dict[str, float] = {
        entry["chapter_id"]: entry["weakness_boost"]
        for entry in top_mistake_chapters
    }

    enriched: list[dict[str, Any]] = []
    for task in tasks:
        task_copy = dict(task)

        base_weakness = clamp(float(task_copy.get("weakness_score") or 0.5))
        chapter_id = task_copy.get("chapter_id")
        subject_id = task_copy.get("subject_id")

        # Signal 1 — mistake chapter boost
        mistake_boost = chapter_boost.get(chapter_id, 0.0) if chapter_id else 0.0

        # Signal 2 — test performance weakness
        subject_weakness = subject_weakness_map.get(subject_id, 0.0) if subject_id else 0.0

        enriched_weakness = clamp(
            base_weakness
            + mistake_weight * mistake_boost
            + test_weight * subject_weakness
        )

        if enriched_weakness != base_weakness:
            task_copy["weakness_score"] = enriched_weakness
            logger.debug(
                "Enriched weakness for task %s (chapter=%s, subject=%s): "
                "%.4f → %.4f (mistake_boost=%.4f, subject_weakness=%.4f)",
                task_copy.get("id", "?"),
                chapter_id,
                subject_id,
                base_weakness,
                enriched_weakness,
                mistake_boost,
                subject_weakness,
            )

        # Recompute priority score with the enriched weakness value
        factors = PriorityFactors(
            weakness_score=task_copy.get("weakness_score", 0.5),
            deadline_pressure=clamp(float(task_copy.get("deadline_pressure") or 0.5)),
            board_weightage=clamp(float(task_copy.get("board_weightage") or 0.5)),
            backlog_score=clamp(float(task_copy.get("backlog_score") or 0.5)),
            revision_due_score=clamp(float(task_copy.get("revision_due_score") or 0.5)),
        )
        task_copy["priority_score"] = compute_priority_score(factors)

        enriched.append(task_copy)

    return enriched


# ---------------------------------------------------------------------------
# Helper: parse AI response into a task list
# ---------------------------------------------------------------------------


def _parse_plan(response_text: str, pending_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse *response_text* into a list of task dicts.

    Tries ``json.loads()`` first.  If the response is not valid JSON (or is
    not a list at the top level), falls back to a rule-based plan: the pending
    tasks sorted by ``priority_score`` descending, each assigned a default
    90-minute duration if not already present.

    Args:
        response_text: Raw string returned by ask_tillu().
        pending_tasks: Current pending study_tasks from the DB.

    Returns:
        List of task dicts, each expected to have at minimum
        ``estimated_duration_min``.  ``chapter_start_time`` and
        ``chapter_end_time`` (HH:MM) are optional but used for overlap checks.
    """
    try:
        parsed = json.loads(response_text)
        if isinstance(parsed, list):
            logger.info("Planner: AI returned valid JSON task list (%d items)", len(parsed))
            return parsed
        if isinstance(parsed, dict) and "tasks" in parsed:
            logger.info("Planner: AI returned JSON object with 'tasks' key")
            return parsed["tasks"]
    except (json.JSONDecodeError, ValueError):
        pass

    logger.warning("Planner: AI response is not valid JSON — falling back to rule-based plan")
    sorted_tasks = sorted(
        pending_tasks,
        key=lambda t: t.get("priority_score", 0.0),
        reverse=True,
    )
    # Ensure each task has a duration field
    fallback = []
    for t in sorted_tasks:
        task_copy = dict(t)
        if "estimated_duration_min" not in task_copy or task_copy["estimated_duration_min"] is None:
            task_copy["estimated_duration_min"] = 90
        fallback.append(task_copy)
    return fallback


# ---------------------------------------------------------------------------
# Main: run_nightly_plan
# ---------------------------------------------------------------------------


async def run_nightly_plan() -> None:
    """Generate and persist tomorrow's study schedule.

    Steps:
    1. Fetch sleep window from sleep_agent.
    2. Compute available_minutes from sleep duration.
    3. Fetch pending study_tasks, top-10 mistake chapters, and test summary.
    4. Call ask_tillu() to get a proposed plan.
    5. Parse the response; fall back to priority-sorted pending tasks on failure.
    6. For each proposed task, skip any that overlap the sleep window.
    7. Enforce the daily budget (stop when cumulative minutes would exceed it).
    8. Insert valid tasks for tomorrow via create_task().
    9. Broadcast ``daily_plan_created`` WebSocket event.
    """
    tomorrow = date.today() + timedelta(days=1)
    db = get_client()

    # Step 1 — sleep window
    sleep_start, sleep_end = await get_sleep_window()

    # Step 2 — available minutes
    sleep_duration_hours = _compute_sleep_duration(sleep_start, sleep_end)
    available_minutes = int((24 - sleep_duration_hours) * 60)
    logger.info(
        "Planner: sleep window %s–%s (%.2f h) → %d available minutes",
        sleep_start,
        sleep_end,
        sleep_duration_hours,
        available_minutes,
    )

    # Step 3 — context data
    pending_tasks_result = (
        db.table("study_tasks").select("*").eq("status", "pending").execute()
    )
    pending_tasks: list[dict[str, Any]] = pending_tasks_result.data or []

    top_mistakes = _get_top_mistake_chapters(db)

    test_result = db.table("tests").select("subject_id, percentage").execute()
    # Build per-subject average from raw rows (mirrors /tests/summary logic)
    raw_tests: list[dict[str, Any]] = test_result.data or []
    from collections import defaultdict as _defaultdict
    _groups: dict[str, list[float]] = _defaultdict(list)
    for row in raw_tests:
        if row.get("percentage") is not None:
            _groups[row["subject_id"]].append(float(row["percentage"]))
    test_summary: list[dict[str, Any]] = [
        {"subject_id": sid, "avg_percentage": round(sum(pcts) / len(pcts), 2)}
        for sid, pcts in _groups.items()
    ]

    # Step 3b — context enrichment (Requirements 11.4, 12.5)
    # Build enrichment signals and apply weakness boost to pending tasks so
    # that the AI receives and acts on up-to-date, accuracy-weighted weakness
    # data.
    subject_weakness_map = _build_subject_weakness_map(test_summary)
    enriched_tasks = _enrich_task_weakness(
        pending_tasks, top_mistakes, subject_weakness_map
    )
    logger.info(
        "Planner: enriched %d pending tasks with weakness boost "
        "(top_mistakes=%d, subjects_with_test_data=%d)",
        len(enriched_tasks),
        len(top_mistakes),
        len(subject_weakness_map),
    )

    context: dict[str, Any] = {
        "date": str(tomorrow),
        "sleep_start": sleep_start,
        "sleep_end": sleep_end,
        "available_minutes": available_minutes,
        # Use enriched tasks so the AI sees boosted weakness / priority scores.
        "tasks": enriched_tasks,
        "weak_chapters": top_mistakes,
        "test_summary": test_summary,
        "deadline": "2025-11-30",
    }

    # Step 4 — AI call
    plan_response = await ask_tillu("Generate tomorrow's study plan", context)

    # Step 5 — parse
    # Pass enriched_tasks as the fallback corpus so the rule-based path also
    # benefits from the enriched priority scores.
    proposed_tasks = _parse_plan(plan_response, enriched_tasks)

    # Steps 6 & 7 — filter by sleep-window overlap and budget
    scheduled: list[dict[str, Any]] = []
    cumulative_minutes: int = 0

    for task in proposed_tasks:
        duration = int(task.get("estimated_duration_min", 90) or 90)

        # Budget check — stop if adding this task would exceed available time
        if cumulative_minutes + duration > available_minutes:
            logger.info(
                "Planner: budget exceeded (%d + %d > %d) — stopping",
                cumulative_minutes,
                duration,
                available_minutes,
            )
            break

        # Sleep-window overlap check (only when start/end times are provided)
        task_start = task.get("chapter_start_time") or task.get("start_time")
        task_end = task.get("chapter_end_time") or task.get("end_time")

        if task_start and task_end:
            if sleep_window_overlaps(task_start, task_end, sleep_start, sleep_end):
                logger.info(
                    "Planner: skipping task %s (%s–%s) — overlaps sleep window %s–%s",
                    task.get("chapter_id") or task.get("id", "unknown"),
                    task_start,
                    task_end,
                    sleep_start,
                    sleep_end,
                )
                continue

        # Step 8 — insert into DB for tomorrow
        insert_payload: dict[str, Any] = {
            "scheduled_date": str(tomorrow),
            "estimated_duration_min": duration,
            "status": "pending",
        }
        # Forward optional fields when present
        for field in (
            "subject_id",
            "chapter_id",
            "weakness_score",
            "board_weightage",
            "backlog_score",
            "revision_due_score",
            "priority_score",
        ):
            if field in task and task[field] is not None:
                insert_payload[field] = task[field]

        try:
            created = create_task(insert_payload)
            scheduled.append(created)
            cumulative_minutes += duration
            logger.debug("Planner: inserted task %s (%d min)", created.get("id"), duration)
        except Exception as exc:  # pragma: no cover — DB errors not under test
            logger.error("Planner: failed to insert task: %s", exc)

    # Step 9 — broadcast
    await ws_manager.broadcast(
        {
            "type": "daily_plan_created",
            "date": str(tomorrow),
            "task_count": len(scheduled),
        }
    )
    logger.info(
        "Planner: nightly plan complete — %d tasks scheduled for %s",
        len(scheduled),
        tomorrow,
    )


# ---------------------------------------------------------------------------
# Main: check_missed_tasks
# ---------------------------------------------------------------------------


async def check_missed_tasks() -> None:
    """Mark past-date pending tasks as 'missed' and broadcast events.

    Queries ``study_tasks`` for rows with ``status='pending'`` whose
    ``scheduled_date`` is strictly before today.  Each such task is updated
    to ``status='missed'`` and a ``task_update`` WebSocket event is broadcast.
    """
    today = date.today()
    db = get_client()

    result = (
        db.table("study_tasks")
        .select("id, scheduled_date, estimated_duration_min")
        .eq("status", "pending")
        .execute()
    )
    tasks = result.data or []

    for task in tasks:
        raw_date = task.get("scheduled_date")
        if raw_date is None:
            continue

        # Parse scheduled_date
        if isinstance(raw_date, date):
            scheduled_date = raw_date
        else:
            try:
                scheduled_date = date.fromisoformat(str(raw_date))
            except ValueError:
                logger.warning("Planner: cannot parse scheduled_date %r for task %s", raw_date, task.get("id"))
                continue

        # Only mark tasks from strictly before today as missed
        if scheduled_date < today:
            task_id = task["id"]
            try:
                update_task(task_id, {"status": "missed"})
                await ws_manager.broadcast(
                    {"type": "task_update", "task_id": task_id, "status": "missed"}
                )
                logger.info("Planner: task %s marked missed (scheduled_date=%s)", task_id, scheduled_date)
            except Exception as exc:  # pragma: no cover
                logger.error("Planner: failed to mark task %s as missed: %s", task_id, exc)
