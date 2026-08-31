"""Task service layer for Tillu AI Study OS.

Provides ``create_task`` and ``update_task`` as the single source of truth for
writing to the ``study_tasks`` table.  Both functions:

1. Accept a payload dict with the task fields.
2. Extract the five priority-score factors from the payload (defaulting to 0.5
   for any that are absent).
3. Use ``compute_deadline_pressure`` for ``deadline_pressure`` when the caller
   does not supply it explicitly.
4. Compute the priority score via ``compute_priority_score`` from
   ``app.priority``.
5. Persist ``priority_score`` alongside the other fields in Supabase.
6. Return the full inserted / updated row as a dict.

This enforces Requirements 5.2 and 5.3: the score is always persisted on
create *and* recomputed on every update that touches any factor field.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.db import get_client
from app.priority import (
    PriorityFactors,
    compute_deadline_pressure,
    compute_priority_score,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Fields whose presence in an update payload must trigger score recomputation.
_FACTOR_FIELDS: frozenset[str] = frozenset(
    {
        "weakness_score",
        "deadline_pressure",
        "board_weightage",
        "backlog_score",
        "revision_due_score",
        "scheduled_date",  # changing the date shifts deadline_pressure
    }
)

_DEFAULT_FACTOR = 0.5


def _extract_factors(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> PriorityFactors:
    """Build a ``PriorityFactors`` from *payload*, falling back to *existing*
    values and then to ``_DEFAULT_FACTOR``.

    ``deadline_pressure`` is special:
    - If the caller supplies it explicitly → use it directly.
    - Otherwise, derive it from ``scheduled_date`` (payload first, then
      existing) using ``compute_deadline_pressure``.
    """
    def _get(field: str, default: float = _DEFAULT_FACTOR) -> float:
        if field in payload:
            return float(payload[field])
        if existing and field in existing and existing[field] is not None:
            return float(existing[field])
        return default

    # Determine deadline_pressure
    if "deadline_pressure" in payload:
        deadline_pressure = float(payload["deadline_pressure"])
    else:
        # Resolve scheduled_date for the pressure calculation
        raw_date = payload.get("scheduled_date") or (existing or {}).get("scheduled_date")
        if raw_date is not None:
            if isinstance(raw_date, str):
                scheduled_date = date.fromisoformat(raw_date)
            else:
                scheduled_date = raw_date  # already a date object
            deadline_pressure = compute_deadline_pressure(scheduled_date)
        else:
            # No date available — use the default factor
            deadline_pressure = _DEFAULT_FACTOR

    return PriorityFactors(
        weakness_score=_get("weakness_score"),
        deadline_pressure=deadline_pressure,
        board_weightage=_get("board_weightage"),
        backlog_score=_get("backlog_score"),
        revision_due_score=_get("revision_due_score"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Insert a new row into ``study_tasks`` and return it.

    The five priority-score factors are read from *payload* (defaulting to
    ``0.5`` when absent).  ``priority_score`` is computed and included in
    the INSERT so it is persisted from the very first write.

    Args:
        payload: Arbitrary task fields.  Must include at minimum the columns
                 required by the ``study_tasks`` table NOT NULL constraints
                 (e.g. ``scheduled_date``, ``estimated_duration_min``).

    Returns:
        The full row dict as returned by Supabase after the insert.

    Raises:
        RuntimeError: If the Supabase insert fails or returns no data.
    """
    factors = _extract_factors(payload)
    score = compute_priority_score(factors)

    insert_data = {**payload, "priority_score": score}

    result = get_client().table("study_tasks").insert(insert_data).execute()

    if not result.data:
        raise RuntimeError(
            f"study_tasks insert returned no data. Supabase response: {result}"
        )
    return result.data[0]


def update_task(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Update an existing ``study_tasks`` row and return the full updated row.

    If *payload* contains any factor field (``weakness_score``,
    ``deadline_pressure``, ``board_weightage``, ``backlog_score``,
    ``revision_due_score``, or ``scheduled_date``), the priority score is
    recomputed and the new value is persisted alongside the other changes.

    When a factor field is missing from *payload*, the existing DB value is
    used for the recomputation so the score always reflects the current state
    of all five factors.

    Args:
        task_id: UUID string identifying the task in ``study_tasks``.
        payload: Fields to update.  At least one field is expected.

    Returns:
        The full updated row dict as returned by Supabase.

    Raises:
        RuntimeError: If the task is not found or the Supabase update fails.
    """
    db = get_client()

    should_recompute = bool(_FACTOR_FIELDS & payload.keys())

    if should_recompute:
        # Fetch the current row to fill in any missing factor values.
        fetch_result = (
            db.table("study_tasks")
            .select(
                "weakness_score, deadline_pressure, board_weightage, "
                "backlog_score, revision_due_score, scheduled_date"
            )
            .eq("id", task_id)
            .limit(1)
            .execute()
        )
        if not fetch_result.data:
            raise RuntimeError(
                f"study_tasks row with id={task_id!r} not found — cannot recompute priority score."
            )
        existing = fetch_result.data[0]
        factors = _extract_factors(payload, existing)
        score = compute_priority_score(factors)
        update_data = {**payload, "priority_score": score}
    else:
        update_data = payload

    result = (
        db.table("study_tasks")
        .update(update_data)
        .eq("id", task_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(
            f"study_tasks update for id={task_id!r} returned no data. "
            f"Supabase response: {result}"
        )
    return result.data[0]
