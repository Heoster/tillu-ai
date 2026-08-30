"""Unit tests for backend/app/priority.py.

Covers:
- clamp() edge cases and normal values
- compute_priority_score() formula correctness with known inputs
- compute_priority_score() output always in [0.0, 1.0] (including extreme inputs)
- compute_deadline_pressure() boundary behaviour
"""

import pytest
from datetime import date, timedelta

from app.priority import (
    DEADLINE,
    PriorityFactors,
    clamp,
    compute_deadline_pressure,
    compute_priority_score,
)


# ---------------------------------------------------------------------------
# clamp()
# ---------------------------------------------------------------------------

class TestClamp:
    def test_value_below_zero_clamped_to_zero(self):
        assert clamp(-5.0) == 0.0

    def test_value_above_one_clamped_to_one(self):
        assert clamp(2.5) == 1.0

    def test_zero_unchanged(self):
        assert clamp(0.0) == 0.0

    def test_one_unchanged(self):
        assert clamp(1.0) == 1.0

    def test_mid_range_unchanged(self):
        assert clamp(0.5) == 0.5

    def test_very_large_negative(self):
        assert clamp(-1e9) == 0.0

    def test_very_large_positive(self):
        assert clamp(1e9) == 1.0

    def test_integer_input_coerced_to_float(self):
        result = clamp(0)
        assert isinstance(result, float)
        assert result == 0.0


# ---------------------------------------------------------------------------
# compute_priority_score()
# ---------------------------------------------------------------------------

class TestComputePriorityScore:
    def _factors(self, w=0.0, d=0.0, b=0.0, bk=0.0, r=0.0) -> PriorityFactors:
        return PriorityFactors(
            weakness_score=w,
            deadline_pressure=d,
            board_weightage=b,
            backlog_score=bk,
            revision_due_score=r,
        )

    # --- Formula correctness with pre-normalised inputs ---

    def test_all_zeros_gives_zero(self):
        assert compute_priority_score(self._factors()) == 0.0

    def test_all_ones_gives_one(self):
        result = compute_priority_score(self._factors(1, 1, 1, 1, 1))
        # 0.35 + 0.25 + 0.20 + 0.10 + 0.10 = 1.0
        assert result == pytest.approx(1.0, abs=1e-9)

    def test_only_weakness_weight(self):
        # Only weakness=1, rest zero → 0.35 * 1 = 0.35
        result = compute_priority_score(self._factors(w=1.0))
        assert result == pytest.approx(0.35, abs=1e-9)

    def test_only_deadline_weight(self):
        result = compute_priority_score(self._factors(d=1.0))
        assert result == pytest.approx(0.25, abs=1e-9)

    def test_only_board_weightage(self):
        result = compute_priority_score(self._factors(b=1.0))
        assert result == pytest.approx(0.20, abs=1e-9)

    def test_only_backlog_weight(self):
        result = compute_priority_score(self._factors(bk=1.0))
        assert result == pytest.approx(0.10, abs=1e-9)

    def test_only_revision_weight(self):
        result = compute_priority_score(self._factors(r=1.0))
        assert result == pytest.approx(0.10, abs=1e-9)

    def test_known_mixed_values(self):
        # w=0.8, d=0.6, b=0.5, bk=0.4, r=0.2
        # 0.35*0.8 + 0.25*0.6 + 0.20*0.5 + 0.10*0.4 + 0.10*0.2
        # = 0.28 + 0.15 + 0.10 + 0.04 + 0.02 = 0.59
        result = compute_priority_score(self._factors(0.8, 0.6, 0.5, 0.4, 0.2))
        assert result == pytest.approx(0.59, abs=1e-6)

    def test_weights_sum_to_one(self):
        """Verify the formula coefficients sum to 1.0 (sanity check)."""
        weights = [0.35, 0.25, 0.20, 0.10, 0.10]
        assert sum(weights) == pytest.approx(1.0, abs=1e-9)

    # --- Output always in [0.0, 1.0] ---

    def test_output_in_range_for_unclamped_inputs(self):
        # Extreme out-of-range inputs must still yield [0, 1]
        result = compute_priority_score(self._factors(999, -999, 500, -1, 2))
        assert 0.0 <= result <= 1.0

    def test_negative_inputs_clamped(self):
        result = compute_priority_score(self._factors(-1, -1, -1, -1, -1))
        assert result == 0.0

    def test_oversized_inputs_clamped(self):
        result = compute_priority_score(self._factors(10, 10, 10, 10, 10))
        assert result == pytest.approx(1.0, abs=1e-9)

    def test_return_rounded_to_6_decimal_places(self):
        # 0.35*0.1 + 0.25*0.1 + 0.20*0.1 + 0.10*0.1 + 0.10*0.1 = 0.1
        result = compute_priority_score(self._factors(0.1, 0.1, 0.1, 0.1, 0.1))
        # Confirm it's rounded (not more than 6 decimal places)
        assert result == round(result, 6)


# ---------------------------------------------------------------------------
# compute_deadline_pressure()
# ---------------------------------------------------------------------------

class TestComputeDeadlinePressure:
    def test_deadline_day_returns_one(self):
        assert compute_deadline_pressure(DEADLINE) == 1.0

    def test_past_deadline_returns_one(self):
        past = DEADLINE + timedelta(days=10)
        assert compute_deadline_pressure(past) == 1.0

    def test_far_future_returns_low_pressure(self):
        # 180 days before deadline → 1 - 180/180 = 0.0
        far_future = DEADLINE - timedelta(days=180)
        result = compute_deadline_pressure(far_future)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_beyond_180_days_clamped_to_zero(self):
        # 200 days before deadline → 1 - 200/180 < 0 → clamped to 0
        very_far = DEADLINE - timedelta(days=200)
        result = compute_deadline_pressure(very_far)
        assert result == 0.0

    def test_pressure_increases_as_deadline_approaches(self):
        day_far = DEADLINE - timedelta(days=90)
        day_close = DEADLINE - timedelta(days=30)
        assert compute_deadline_pressure(day_far) < compute_deadline_pressure(day_close)

    def test_output_in_range(self):
        for delta in [0, 1, 30, 60, 90, 120, 150, 180, 200]:
            d = DEADLINE - timedelta(days=delta)
            result = compute_deadline_pressure(d)
            assert 0.0 <= result <= 1.0, f"Out of range for delta={delta}: {result}"

    def test_one_day_before_deadline(self):
        one_before = DEADLINE - timedelta(days=1)
        # 1 - 1/180 ≈ 0.9944
        expected = clamp(1.0 - 1 / 180.0)
        assert compute_deadline_pressure(one_before) == pytest.approx(expected, abs=1e-9)
