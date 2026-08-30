"""Priority Score engine for Tillu AI Study OS.

Provides a pure-function priority score computation based on five weighted
factors. All inputs are clamped to [0.0, 1.0] before the formula is applied,
so the result is always within that interval.
"""

from dataclasses import dataclass
from datetime import date


def _deadline_for_year(year: int) -> date:
    """Return 30 November for the given year."""
    return date(year, 11, 30)


def _current_deadline() -> date:
    """Return the nearest upcoming 30 November (or today if today is that date)."""
    today = date.today()
    candidate = _deadline_for_year(today.year)
    # If this year's deadline has already passed, use next year's
    if today > candidate:
        return _deadline_for_year(today.year + 1)
    return candidate


# Module-level constant evaluated once at import time.
DEADLINE: date = _current_deadline()


@dataclass
class PriorityFactors:
    """Five normalised input factors for the priority score formula.

    All fields should be in [0.0, 1.0]. Out-of-range values are clamped
    inside ``compute_priority_score``.
    """

    weakness_score: float       # How weak the student is in this chapter
    deadline_pressure: float    # How close the exam deadline is
    board_weightage: float      # How heavily this chapter is weighted in board exams
    backlog_score: float        # How much pending backlog exists for this chapter
    revision_due_score: float   # How overdue the chapter is for revision


def clamp(value: float) -> float:
    """Clamp *value* to the closed interval [0.0, 1.0].

    Args:
        value: Any real number (including values outside [0, 1]).

    Returns:
        A float guaranteed to be in [0.0, 1.0].
    """
    return max(0.0, min(1.0, float(value)))


def compute_priority_score(factors: PriorityFactors) -> float:
    """Compute the weighted priority score from five input factors.

    Formula::

        score = 0.35·w + 0.25·d + 0.20·b + 0.10·bk + 0.10·r

    where each factor is first clamped to [0.0, 1.0].

    Args:
        factors: A :class:`PriorityFactors` instance (values need not be
                 pre-clamped; clamping is applied internally).

    Returns:
        A float in [0.0, 1.0] rounded to 6 decimal places.
    """
    w  = clamp(factors.weakness_score)
    d  = clamp(factors.deadline_pressure)
    b  = clamp(factors.board_weightage)
    bk = clamp(factors.backlog_score)
    r  = clamp(factors.revision_due_score)
    return round(0.35 * w + 0.25 * d + 0.20 * b + 0.10 * bk + 0.10 * r, 6)


def compute_deadline_pressure(scheduled_date: date) -> float:
    """Compute deadline pressure based on days remaining until 30 November.

    Pressure scales linearly from 0.0 (180 days out) to 1.0 (deadline day or
    past). Any date on or after the deadline returns 1.0.

    Args:
        scheduled_date: The date for which pressure is being evaluated.

    Returns:
        A float in [0.0, 1.0].
    """
    days_remaining = (DEADLINE - scheduled_date).days
    if days_remaining <= 0:
        return 1.0
    return clamp(1.0 - days_remaining / 180.0)
