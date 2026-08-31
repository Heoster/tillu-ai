"""Unit tests for backend/app/services/task_service.py.

All Supabase I/O is replaced with lightweight mocks so the tests run without
a live database connection.

Covers:
- create_task: priority score computed and stored in insert payload
- create_task: factor defaults (0.5) applied when fields are absent
- create_task: deadline_pressure derived from scheduled_date when not supplied
- create_task: raises RuntimeError when Supabase returns no data
- update_task: priority score recomputed when any factor field changes
- update_task: priority score recomputed when scheduled_date changes
- update_task: priority score NOT recomputed when no factor field changes
- update_task: existing DB values merged for missing factors in the payload
- update_task: raises RuntimeError when task is not found
- update_task: raises RuntimeError when Supabase update returns no data
- _extract_factors: honours explicitly supplied deadline_pressure
"""

from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from app.priority import (
    PriorityFactors,
    compute_deadline_pressure,
    compute_priority_score,
)
from app.services.task_service import (
    _DEFAULT_FACTOR,
    _FACTOR_FIELDS,
    _extract_factors,
    create_task,
    update_task,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_result(data: list | None):
    """Return a mock Supabase result object with a .data attribute."""
    m = MagicMock()
    m.data = data if data is not None else []
    return m


class _TableMock:
    """A thin mock of the Supabase table interface.

    Stores the insert_data and update_data passed to insert()/update() so
    tests can inspect them after the fact without calling db.table() again.
    """

    def __init__(self, insert_result=None, update_result=None, select_result=None):
        self._insert_result = insert_result or _mock_result([{"id": "task-1", "priority_score": 0.5}])
        self._update_result = update_result or _mock_result([{"id": "task-1", "priority_score": 0.5}])
        self._select_result = select_result or _mock_result([])

        # Public attributes tests can read after the service call
        self.inserted_data: dict | None = None
        self.updated_data: dict | None = None
        self.select_called: bool = False

    # --- Supabase chain methods ---

    def insert(self, data: dict):
        self.inserted_data = data
        chain = MagicMock()
        chain.execute.return_value = self._insert_result
        return chain

    def select(self, *args, **kwargs):
        self.select_called = True
        chain = MagicMock()
        chain.eq = lambda *a, **kw: chain
        chain.limit = lambda *a, **kw: chain
        chain.execute.return_value = self._select_result
        return chain

    def update(self, data: dict):
        self.updated_data = data
        chain = MagicMock()
        chain.eq = lambda *a, **kw: chain
        chain.execute.return_value = self._update_result
        return chain


def _make_db_mock(insert_result=None, update_result=None, select_result=None):
    """Build a Supabase client mock that returns a _TableMock for every table()."""
    table = _TableMock(
        insert_result=insert_result,
        update_result=update_result,
        select_result=select_result,
    )
    db = MagicMock()
    db.table.return_value = table
    # Expose the table mock on db for test inspection
    db._table = table
    return db


# ---------------------------------------------------------------------------
# _extract_factors helpers
# ---------------------------------------------------------------------------

class TestExtractFactors:
    def test_all_factors_from_payload(self):
        payload = {
            "weakness_score": 0.8,
            "deadline_pressure": 0.6,
            "board_weightage": 0.4,
            "backlog_score": 0.3,
            "revision_due_score": 0.2,
        }
        factors = _extract_factors(payload)
        assert factors.weakness_score == pytest.approx(0.8)
        assert factors.deadline_pressure == pytest.approx(0.6)
        assert factors.board_weightage == pytest.approx(0.4)
        assert factors.backlog_score == pytest.approx(0.3)
        assert factors.revision_due_score == pytest.approx(0.2)

    def test_defaults_when_payload_empty(self):
        factors = _extract_factors({})
        assert factors.weakness_score == _DEFAULT_FACTOR
        assert factors.deadline_pressure == _DEFAULT_FACTOR
        assert factors.board_weightage == _DEFAULT_FACTOR
        assert factors.backlog_score == _DEFAULT_FACTOR
        assert factors.revision_due_score == _DEFAULT_FACTOR

    def test_deadline_pressure_derived_from_scheduled_date(self):
        from app.priority import DEADLINE
        from datetime import timedelta
        target_date = DEADLINE - timedelta(days=90)
        payload = {"scheduled_date": str(target_date)}
        factors = _extract_factors(payload)
        expected = compute_deadline_pressure(target_date)
        assert factors.deadline_pressure == pytest.approx(expected)

    def test_explicit_deadline_pressure_overrides_date_derivation(self):
        payload = {
            "scheduled_date": "2024-06-01",
            "deadline_pressure": 0.99,
        }
        factors = _extract_factors(payload)
        assert factors.deadline_pressure == pytest.approx(0.99)

    def test_existing_values_fill_missing_payload_fields(self):
        existing = {
            "weakness_score": 0.7,
            "deadline_pressure": 0.5,
            "board_weightage": 0.3,
            "backlog_score": 0.1,
            "revision_due_score": 0.9,
            "scheduled_date": None,
        }
        # payload only supplies weakness_score
        payload = {"weakness_score": 0.2}
        factors = _extract_factors(payload, existing)
        assert factors.weakness_score == pytest.approx(0.2)       # from payload
        assert factors.board_weightage == pytest.approx(0.3)      # from existing
        assert factors.backlog_score == pytest.approx(0.1)        # from existing
        assert factors.revision_due_score == pytest.approx(0.9)   # from existing

    def test_scheduled_date_as_date_object(self):
        from app.priority import DEADLINE
        from datetime import timedelta
        d = DEADLINE - timedelta(days=45)
        factors = _extract_factors({"scheduled_date": d})
        assert factors.deadline_pressure == pytest.approx(compute_deadline_pressure(d))


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------

class TestCreateTask:
    def test_priority_score_in_insert_payload(self):
        """create_task must include priority_score in the data passed to insert()."""
        expected_score = compute_priority_score(
            PriorityFactors(
                weakness_score=0.8,
                deadline_pressure=0.6,
                board_weightage=0.4,
                backlog_score=0.3,
                revision_due_score=0.2,
            )
        )
        returned_row = {"id": "new-1", "priority_score": expected_score}
        db = _make_db_mock(insert_result=_mock_result([returned_row]))

        with patch("app.services.task_service.get_client", return_value=db):
            create_task(
                {
                    "weakness_score": 0.8,
                    "deadline_pressure": 0.6,
                    "board_weightage": 0.4,
                    "backlog_score": 0.3,
                    "revision_due_score": 0.2,
                    "scheduled_date": "2025-01-01",
                    "estimated_duration_min": 60,
                }
            )

        assert "priority_score" in db._table.inserted_data
        assert db._table.inserted_data["priority_score"] == pytest.approx(expected_score)

    def test_returns_row_from_supabase(self):
        returned_row = {"id": "abc", "priority_score": 0.35}
        db = _make_db_mock(insert_result=_mock_result([returned_row]))

        with patch("app.services.task_service.get_client", return_value=db):
            result = create_task({"estimated_duration_min": 30})

        assert result == returned_row

    def test_default_factors_applied_when_absent(self):
        """When no factor fields are in the payload, all default to 0.5."""
        expected_score = compute_priority_score(
            PriorityFactors(
                weakness_score=_DEFAULT_FACTOR,
                deadline_pressure=_DEFAULT_FACTOR,
                board_weightage=_DEFAULT_FACTOR,
                backlog_score=_DEFAULT_FACTOR,
                revision_due_score=_DEFAULT_FACTOR,
            )
        )
        returned_row = {"id": "def-1", "priority_score": expected_score}
        db = _make_db_mock(insert_result=_mock_result([returned_row]))

        with patch("app.services.task_service.get_client", return_value=db):
            create_task({"estimated_duration_min": 45})

        assert db._table.inserted_data["priority_score"] == pytest.approx(expected_score)

    def test_raises_runtime_error_when_no_data_returned(self):
        db = _make_db_mock(insert_result=_mock_result([]))

        with patch("app.services.task_service.get_client", return_value=db):
            with pytest.raises(RuntimeError, match="insert returned no data"):
                create_task({"estimated_duration_min": 30})

    def test_deadline_pressure_auto_computed_from_date(self):
        from app.priority import DEADLINE
        from datetime import timedelta
        target = DEADLINE - timedelta(days=60)
        expected_dp = compute_deadline_pressure(target)
        payload = {
            "weakness_score": 0.5,
            "board_weightage": 0.5,
            "backlog_score": 0.5,
            "revision_due_score": 0.5,
            "scheduled_date": str(target),
            "estimated_duration_min": 30,
        }
        expected_score = compute_priority_score(
            PriorityFactors(
                weakness_score=0.5,
                deadline_pressure=expected_dp,
                board_weightage=0.5,
                backlog_score=0.5,
                revision_due_score=0.5,
            )
        )
        returned_row = {"id": "x", "priority_score": expected_score}
        db = _make_db_mock(insert_result=_mock_result([returned_row]))

        with patch("app.services.task_service.get_client", return_value=db):
            create_task(payload)

        assert db._table.inserted_data["priority_score"] == pytest.approx(expected_score)

    def test_original_payload_fields_preserved_in_insert(self):
        """All original payload fields must be forwarded to the insert call."""
        returned_row = {"id": "z", "priority_score": 0.5}
        db = _make_db_mock(insert_result=_mock_result([returned_row]))

        payload = {
            "subject_id": "subj-1",
            "chapter_id": "chap-1",
            "scheduled_date": "2025-03-01",
            "estimated_duration_min": 90,
        }

        with patch("app.services.task_service.get_client", return_value=db):
            create_task(payload)

        assert db._table.inserted_data["subject_id"] == "subj-1"
        assert db._table.inserted_data["chapter_id"] == "chap-1"
        assert db._table.inserted_data["estimated_duration_min"] == 90


# ---------------------------------------------------------------------------
# update_task
# ---------------------------------------------------------------------------

class TestUpdateTask:
    def _existing_row(self, **overrides) -> dict:
        base = {
            "weakness_score": 0.5,
            "deadline_pressure": 0.5,
            "board_weightage": 0.5,
            "backlog_score": 0.5,
            "revision_due_score": 0.5,
            "scheduled_date": "2025-06-01",
        }
        return {**base, **overrides}

    def test_priority_score_recomputed_on_factor_change(self):
        """When weakness_score changes, priority_score must be recomputed.

        When the existing row has a scheduled_date but deadline_pressure is
        not in the payload, _extract_factors derives deadline_pressure from
        the scheduled_date (not from the stored deadline_pressure column).
        The expected score must reflect this derivation.
        """
        existing = self._existing_row(weakness_score=0.3)
        new_weakness = 0.9
        payload = {"weakness_score": new_weakness}

        # deadline_pressure will be derived from scheduled_date (existing["scheduled_date"])
        derived_dp = compute_deadline_pressure(date.fromisoformat(existing["scheduled_date"]))
        expected_score = compute_priority_score(
            PriorityFactors(
                weakness_score=new_weakness,
                deadline_pressure=derived_dp,
                board_weightage=existing["board_weightage"],
                backlog_score=existing["backlog_score"],
                revision_due_score=existing["revision_due_score"],
            )
        )
        updated_row = {"id": "task-1", "weakness_score": new_weakness, "priority_score": expected_score}
        db = _make_db_mock(
            select_result=_mock_result([existing]),
            update_result=_mock_result([updated_row]),
        )

        with patch("app.services.task_service.get_client", return_value=db):
            update_task("task-1", payload)

        assert "priority_score" in db._table.updated_data
        assert db._table.updated_data["priority_score"] == pytest.approx(expected_score)

    def test_priority_score_not_recomputed_for_non_factor_update(self):
        """Updating only status must NOT add priority_score to the update payload."""
        payload = {"status": "completed"}
        returned_row = {"id": "task-1", "status": "completed"}
        db = _make_db_mock(update_result=_mock_result([returned_row]))

        with patch("app.services.task_service.get_client", return_value=db):
            update_task("task-1", payload)

        # priority_score must NOT be injected when no factor changed
        assert "priority_score" not in db._table.updated_data

    def test_select_not_called_for_non_factor_update(self):
        """DB fetch should be skipped when the payload has no factor fields."""
        payload = {"actual_duration_min": 45}
        returned_row = {"id": "task-1", "actual_duration_min": 45}
        db = _make_db_mock(update_result=_mock_result([returned_row]))

        with patch("app.services.task_service.get_client", return_value=db):
            update_task("task-1", payload)

        assert not db._table.select_called

    def test_existing_factors_used_for_missing_payload_factors(self):
        """When only one factor is in payload, the rest come from the DB row.

        deadline_pressure is derived from scheduled_date (present in existing row)
        rather than from the stored deadline_pressure column, because the service
        always prefers computing deadline_pressure from the date when available.
        """
        existing = self._existing_row(
            weakness_score=0.2,
            board_weightage=0.8,
            backlog_score=0.1,
            revision_due_score=0.7,
        )
        payload = {"weakness_score": 0.9}  # only this factor is changing

        # deadline_pressure derived from existing["scheduled_date"]
        derived_dp = compute_deadline_pressure(date.fromisoformat(existing["scheduled_date"]))
        expected_score = compute_priority_score(
            PriorityFactors(
                weakness_score=0.9,       # from payload
                deadline_pressure=derived_dp,
                board_weightage=0.8,      # from existing
                backlog_score=0.1,        # from existing
                revision_due_score=0.7,   # from existing
            )
        )
        updated_row = {"id": "task-1", "priority_score": expected_score}
        db = _make_db_mock(
            select_result=_mock_result([existing]),
            update_result=_mock_result([updated_row]),
        )

        with patch("app.services.task_service.get_client", return_value=db):
            update_task("task-1", payload)

        assert db._table.updated_data["priority_score"] == pytest.approx(expected_score)

    def test_raises_runtime_error_when_task_not_found(self):
        """update_task must raise RuntimeError when select returns empty list."""
        db = _make_db_mock(select_result=_mock_result([]))

        with patch("app.services.task_service.get_client", return_value=db):
            with pytest.raises(RuntimeError, match="not found"):
                update_task("missing-id", {"weakness_score": 0.5})

    def test_raises_runtime_error_when_update_returns_no_data(self):
        existing = self._existing_row()
        db = _make_db_mock(
            select_result=_mock_result([existing]),
            update_result=_mock_result([]),
        )

        with patch("app.services.task_service.get_client", return_value=db):
            with pytest.raises(RuntimeError, match="returned no data"):
                update_task("task-1", {"weakness_score": 0.8})

    def test_returns_updated_row(self):
        existing = self._existing_row()
        updated_row = {"id": "task-1", "priority_score": 0.75, "status": "in-progress"}
        db = _make_db_mock(
            select_result=_mock_result([existing]),
            update_result=_mock_result([updated_row]),
        )

        with patch("app.services.task_service.get_client", return_value=db):
            result = update_task("task-1", {"weakness_score": 0.9})

        assert result == updated_row

    def test_recompute_triggered_by_scheduled_date_change(self):
        """Changing only scheduled_date must trigger score recomputation."""
        existing = self._existing_row()
        from app.priority import DEADLINE
        from datetime import timedelta
        new_date = DEADLINE - timedelta(days=10)

        payload = {"scheduled_date": str(new_date)}
        expected_dp = compute_deadline_pressure(new_date)
        expected_score = compute_priority_score(
            PriorityFactors(
                weakness_score=existing["weakness_score"],
                deadline_pressure=expected_dp,
                board_weightage=existing["board_weightage"],
                backlog_score=existing["backlog_score"],
                revision_due_score=existing["revision_due_score"],
            )
        )
        updated_row = {"id": "task-1", "priority_score": expected_score}
        db = _make_db_mock(
            select_result=_mock_result([existing]),
            update_result=_mock_result([updated_row]),
        )

        with patch("app.services.task_service.get_client", return_value=db):
            update_task("task-1", payload)

        assert db._table.updated_data["priority_score"] == pytest.approx(expected_score)

    def test_non_factor_payload_fields_forwarded_to_update(self):
        """Non-factor fields in the payload must still be passed to Supabase."""
        existing = self._existing_row()
        updated_row = {"id": "task-1", "priority_score": 0.5, "status": "in-progress"}
        db = _make_db_mock(
            select_result=_mock_result([existing]),
            update_result=_mock_result([updated_row]),
        )
        payload = {"weakness_score": 0.6, "status": "in-progress"}

        with patch("app.services.task_service.get_client", return_value=db):
            update_task("task-1", payload)

        assert db._table.updated_data["status"] == "in-progress"
        assert "priority_score" in db._table.updated_data


# ---------------------------------------------------------------------------
# _FACTOR_FIELDS constant
# ---------------------------------------------------------------------------

class TestFactorFieldsConstant:
    def test_contains_all_five_factors(self):
        expected = {
            "weakness_score",
            "deadline_pressure",
            "board_weightage",
            "backlog_score",
            "revision_due_score",
        }
        assert expected.issubset(_FACTOR_FIELDS)

    def test_contains_scheduled_date(self):
        assert "scheduled_date" in _FACTOR_FIELDS
