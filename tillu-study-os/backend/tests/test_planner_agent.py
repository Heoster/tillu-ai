"""Unit tests for backend/app/agents/planner_agent.py.

All external I/O (Supabase, WebSocket, AI providers) is replaced with mocks.

Covers:
1. run_nightly_plan calls get_sleep_window()
2. run_nightly_plan skips tasks that overlap the sleep window
3. run_nightly_plan stops adding tasks when the budget is exceeded
4. run_nightly_plan broadcasts daily_plan_created event
5. check_missed_tasks marks past-date pending tasks as 'missed'
6. check_missed_tasks broadcasts task_update event per missed task
7. check_missed_tasks does NOT mark today's tasks as missed
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _mock_result(data: list) -> MagicMock:
    m = MagicMock()
    m.data = data
    return m


def _make_db_mock(
    pending_tasks: list | None = None,
    mistakes: list | None = None,
    tests: list | None = None,
) -> MagicMock:
    """Return a Supabase client mock that returns configurable table data."""
    pending_tasks = pending_tasks if pending_tasks is not None else []
    mistakes = mistakes if mistakes is not None else []
    tests_data = tests if tests is not None else []

    # Build per-table mocks
    def _make_chain(data: list):
        result = _mock_result(data)
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = result
        return chain

    db = MagicMock()

    def table_side_effect(name: str):
        if name == "study_tasks":
            return _make_chain(pending_tasks)
        if name == "mistakes":
            return _make_chain(mistakes)
        if name == "tests":
            return _make_chain(tests_data)
        return _make_chain([])

    db.table.side_effect = table_side_effect
    return db


def _make_update_db_mock(pending_tasks: list) -> MagicMock:
    """Return a DB mock that supports update().eq().execute() chains for check_missed_tasks."""
    db = MagicMock()

    def table_side_effect(name: str):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.update.return_value = chain
        result = _mock_result(pending_tasks)
        chain.execute.return_value = result
        return chain

    db.table.side_effect = table_side_effect
    return db


# ---------------------------------------------------------------------------
# Test 1 — run_nightly_plan calls get_sleep_window()
# ---------------------------------------------------------------------------

class TestRunNightlyPlanCallsGetSleepWindow:
    @pytest.mark.asyncio
    async def test_get_sleep_window_is_called(self):
        db = _make_db_mock()

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ) as mock_gsw,
            patch(
                "app.agents.planner_agent.ask_tillu",
                new_callable=AsyncMock,
                return_value="[]",
            ),
            patch(
                "app.agents.planner_agent.create_task",
                return_value={"id": "t1", "estimated_duration_min": 60},
            ),
            patch(
                "app.agents.planner_agent.ws_manager",
            ) as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        mock_gsw.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 2 — run_nightly_plan skips tasks that overlap the sleep window
# ---------------------------------------------------------------------------

class TestRunNightlyPlanSkipsOverlappingTasks:
    @pytest.mark.asyncio
    async def test_overlapping_task_is_not_inserted(self):
        """A task with start/end times inside the sleep window must be skipped."""
        # Sleep 23:00–06:00; task 00:00–01:00 overlaps
        db = _make_db_mock()
        overlapping_task = {
            "id": "overlap-task",
            "estimated_duration_min": 60,
            "chapter_start_time": "00:00",
            "chapter_end_time": "01:00",
            "priority_score": 0.9,
        }
        non_overlapping_task = {
            "id": "safe-task",
            "estimated_duration_min": 60,
            "chapter_start_time": "10:00",
            "chapter_end_time": "11:00",
            "priority_score": 0.5,
        }

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch(
                "app.agents.planner_agent.ask_tillu",
                new_callable=AsyncMock,
                return_value="[]",
            ),
            patch(
                "app.agents.planner_agent._parse_plan",
                return_value=[overlapping_task, non_overlapping_task],
            ),
            patch(
                "app.agents.planner_agent.create_task",
                return_value={"id": "safe-task", "estimated_duration_min": 60},
            ) as mock_create,
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        # Only one task should have been inserted (the non-overlapping one)
        assert mock_create.call_count == 1
        inserted_payload = mock_create.call_args[0][0]
        # Confirm the inserted task is from the non-overlapping task's duration
        assert inserted_payload["estimated_duration_min"] == 60

    @pytest.mark.asyncio
    async def test_task_without_time_fields_is_not_skipped_on_overlap(self):
        """Tasks without start/end times bypass the overlap check."""
        db = _make_db_mock()
        no_time_task = {
            "id": "no-time-task",
            "estimated_duration_min": 60,
            "priority_score": 0.8,
        }

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch(
                "app.agents.planner_agent.ask_tillu",
                new_callable=AsyncMock,
                return_value="[]",
            ),
            patch(
                "app.agents.planner_agent._parse_plan",
                return_value=[no_time_task],
            ),
            patch(
                "app.agents.planner_agent.create_task",
                return_value={"id": "no-time-task", "estimated_duration_min": 60},
            ) as mock_create,
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        # Task should be inserted even though it has no time fields
        assert mock_create.call_count == 1


# ---------------------------------------------------------------------------
# Test 3 — run_nightly_plan stops when budget is exceeded
# ---------------------------------------------------------------------------

class TestRunNightlyPlanBudgetEnforcement:
    @pytest.mark.asyncio
    async def test_stops_adding_tasks_when_budget_exceeded(self):
        """Tasks that would push cumulative minutes past available_minutes are dropped."""
        # Sleep 22:00–06:00 = 8 hours → available = 16 * 60 = 960 min
        # Proposed tasks: 600 min + 600 min — only the first fits
        db = _make_db_mock()
        task_a = {"id": "task-a", "estimated_duration_min": 600, "priority_score": 0.9}
        task_b = {"id": "task-b", "estimated_duration_min": 600, "priority_score": 0.8}

        created_ids = []

        def fake_create(payload):
            cid = payload.get("estimated_duration_min", 0)
            # Mimic what create_task returns
            row = {"id": f"created-{cid}", "estimated_duration_min": cid}
            created_ids.append(cid)
            return row

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("22:00", "06:00"),
            ),
            patch(
                "app.agents.planner_agent.ask_tillu",
                new_callable=AsyncMock,
                return_value="[]",
            ),
            patch(
                "app.agents.planner_agent._parse_plan",
                return_value=[task_a, task_b],
            ),
            patch(
                "app.agents.planner_agent.create_task",
                side_effect=fake_create,
            ),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        # Only task_a (600 min) should be inserted; task_b would exceed 960 min budget
        assert len(created_ids) == 1
        assert created_ids[0] == 600

    @pytest.mark.asyncio
    async def test_all_tasks_fit_when_within_budget(self):
        """When all tasks fit within the budget, all are inserted."""
        db = _make_db_mock()
        task_a = {"id": "task-a", "estimated_duration_min": 100, "priority_score": 0.9}
        task_b = {"id": "task-b", "estimated_duration_min": 100, "priority_score": 0.8}

        def fake_create(payload):
            return {"id": "x", "estimated_duration_min": payload["estimated_duration_min"]}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch(
                "app.agents.planner_agent.ask_tillu",
                new_callable=AsyncMock,
                return_value="[]",
            ),
            patch(
                "app.agents.planner_agent._parse_plan",
                return_value=[task_a, task_b],
            ),
            patch(
                "app.agents.planner_agent.create_task",
                side_effect=fake_create,
            ) as mock_create,
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        # Both tasks fit (200 min < 1020 min available for 7-hour sleep)
        assert mock_create.call_count == 2


# ---------------------------------------------------------------------------
# Test 4 — run_nightly_plan broadcasts daily_plan_created
# ---------------------------------------------------------------------------

class TestRunNightlyPlanBroadcast:
    @pytest.mark.asyncio
    async def test_broadcasts_daily_plan_created_event(self):
        db = _make_db_mock()

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch(
                "app.agents.planner_agent.ask_tillu",
                new_callable=AsyncMock,
                return_value="[]",
            ),
            patch("app.agents.planner_agent._parse_plan", return_value=[]),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        mock_ws.broadcast.assert_awaited_once()
        broadcast_event = mock_ws.broadcast.call_args[0][0]
        assert broadcast_event["type"] == "daily_plan_created"
        assert "date" in broadcast_event
        assert "task_count" in broadcast_event

    @pytest.mark.asyncio
    async def test_broadcast_task_count_matches_inserted_tasks(self):
        db = _make_db_mock()
        tasks = [
            {"id": f"t{i}", "estimated_duration_min": 30, "priority_score": float(i) / 10}
            for i in range(3)
        ]

        def fake_create(payload):
            return {"id": "x", "estimated_duration_min": payload["estimated_duration_min"]}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch(
                "app.agents.planner_agent.ask_tillu",
                new_callable=AsyncMock,
                return_value="[]",
            ),
            patch("app.agents.planner_agent._parse_plan", return_value=tasks),
            patch("app.agents.planner_agent.create_task", side_effect=fake_create),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        event = mock_ws.broadcast.call_args[0][0]
        assert event["task_count"] == 3


# ---------------------------------------------------------------------------
# Test 5 — check_missed_tasks marks past-date pending tasks as 'missed'
# ---------------------------------------------------------------------------

class TestCheckMissedTasksMarksMissed:
    @pytest.mark.asyncio
    async def test_past_date_task_is_marked_missed(self):
        yesterday = str(date.today() - timedelta(days=1))
        pending_tasks = [
            {"id": "old-task-1", "scheduled_date": yesterday, "estimated_duration_min": 60},
        ]

        db = _make_update_db_mock(pending_tasks)

        updated_ids = []

        def fake_update(task_id, payload):
            if payload.get("status") == "missed":
                updated_ids.append(task_id)
            return {"id": task_id, **payload}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch("app.agents.planner_agent.update_task", side_effect=fake_update),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import check_missed_tasks
            await check_missed_tasks()

        assert "old-task-1" in updated_ids

    @pytest.mark.asyncio
    async def test_multiple_past_tasks_all_marked_missed(self):
        yesterday = str(date.today() - timedelta(days=1))
        two_days_ago = str(date.today() - timedelta(days=2))
        pending_tasks = [
            {"id": "task-1", "scheduled_date": yesterday, "estimated_duration_min": 60},
            {"id": "task-2", "scheduled_date": two_days_ago, "estimated_duration_min": 45},
        ]

        db = _make_update_db_mock(pending_tasks)

        updated_ids = []

        def fake_update(task_id, payload):
            if payload.get("status") == "missed":
                updated_ids.append(task_id)
            return {"id": task_id, **payload}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch("app.agents.planner_agent.update_task", side_effect=fake_update),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import check_missed_tasks
            await check_missed_tasks()

        assert set(updated_ids) == {"task-1", "task-2"}


# ---------------------------------------------------------------------------
# Test 6 — check_missed_tasks broadcasts task_update per missed task
# ---------------------------------------------------------------------------

class TestCheckMissedTasksBroadcasts:
    @pytest.mark.asyncio
    async def test_broadcasts_task_update_for_each_missed_task(self):
        yesterday = str(date.today() - timedelta(days=1))
        pending_tasks = [
            {"id": "missed-1", "scheduled_date": yesterday, "estimated_duration_min": 60},
            {"id": "missed-2", "scheduled_date": yesterday, "estimated_duration_min": 30},
        ]

        db = _make_update_db_mock(pending_tasks)

        def fake_update(task_id, payload):
            return {"id": task_id, **payload}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch("app.agents.planner_agent.update_task", side_effect=fake_update),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import check_missed_tasks
            await check_missed_tasks()

        assert mock_ws.broadcast.await_count == 2
        broadcast_calls = [c[0][0] for c in mock_ws.broadcast.call_args_list]
        for event in broadcast_calls:
            assert event["type"] == "task_update"
            assert event["status"] == "missed"
            assert "task_id" in event

    @pytest.mark.asyncio
    async def test_broadcast_contains_correct_task_id(self):
        yesterday = str(date.today() - timedelta(days=1))
        pending_tasks = [
            {"id": "specific-task-id", "scheduled_date": yesterday, "estimated_duration_min": 60},
        ]

        db = _make_update_db_mock(pending_tasks)

        def fake_update(task_id, payload):
            return {"id": task_id, **payload}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch("app.agents.planner_agent.update_task", side_effect=fake_update),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import check_missed_tasks
            await check_missed_tasks()

        event = mock_ws.broadcast.call_args[0][0]
        assert event["task_id"] == "specific-task-id"


# ---------------------------------------------------------------------------
# Test 7 — check_missed_tasks does NOT mark today's tasks as missed
# ---------------------------------------------------------------------------

class TestCheckMissedTasksDoesNotMarkTodaysMissed:
    @pytest.mark.asyncio
    async def test_todays_task_is_not_marked_missed(self):
        today = str(date.today())
        pending_tasks = [
            {"id": "todays-task", "scheduled_date": today, "estimated_duration_min": 60},
        ]

        db = _make_update_db_mock(pending_tasks)

        updated_ids = []

        def fake_update(task_id, payload):
            if payload.get("status") == "missed":
                updated_ids.append(task_id)
            return {"id": task_id, **payload}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch("app.agents.planner_agent.update_task", side_effect=fake_update),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import check_missed_tasks
            await check_missed_tasks()

        assert "todays-task" not in updated_ids
        mock_ws.broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_future_task_is_not_marked_missed(self):
        tomorrow = str(date.today() + timedelta(days=1))
        pending_tasks = [
            {"id": "future-task", "scheduled_date": tomorrow, "estimated_duration_min": 60},
        ]

        db = _make_update_db_mock(pending_tasks)

        updated_ids = []

        def fake_update(task_id, payload):
            if payload.get("status") == "missed":
                updated_ids.append(task_id)
            return {"id": task_id, **payload}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch("app.agents.planner_agent.update_task", side_effect=fake_update),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import check_missed_tasks
            await check_missed_tasks()

        assert "future-task" not in updated_ids
        mock_ws.broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mixed_dates_only_past_marked_missed(self):
        """When both past and today's tasks are pending, only past ones get marked."""
        yesterday = str(date.today() - timedelta(days=1))
        today = str(date.today())
        pending_tasks = [
            {"id": "old-task", "scheduled_date": yesterday, "estimated_duration_min": 60},
            {"id": "today-task", "scheduled_date": today, "estimated_duration_min": 60},
        ]

        db = _make_update_db_mock(pending_tasks)

        updated_ids = []

        def fake_update(task_id, payload):
            if payload.get("status") == "missed":
                updated_ids.append(task_id)
            return {"id": task_id, **payload}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch("app.agents.planner_agent.update_task", side_effect=fake_update),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import check_missed_tasks
            await check_missed_tasks()

        assert updated_ids == ["old-task"]
        # Only one broadcast (for old-task)
        assert mock_ws.broadcast.await_count == 1


# ---------------------------------------------------------------------------
# Additional unit tests for helpers
# ---------------------------------------------------------------------------

class TestComputeSleepDuration:
    def test_normal_sleep_window_returns_hours(self):
        from app.agents.planner_agent import _compute_sleep_duration
        # 23:00 to 06:00 = 7 hours
        assert _compute_sleep_duration("23:00", "06:00") == pytest.approx(7.0)

    def test_same_day_sleep_window(self):
        from app.agents.planner_agent import _compute_sleep_duration
        # 22:00 to 06:00 = 8 hours
        assert _compute_sleep_duration("22:00", "06:00") == pytest.approx(8.0)

    def test_fallback_to_8_hours_on_http_exception(self):
        from app.agents.planner_agent import _compute_sleep_duration
        from fastapi import HTTPException
        # Patch validate_sleep_log to raise HTTPException → should fall back to 8.0
        with patch(
            "app.agents.planner_agent.validate_sleep_log",
            side_effect=HTTPException(status_code=400, detail="invalid"),
        ):
            result = _compute_sleep_duration("06:00", "06:00")
        assert result == pytest.approx(8.0)


class TestParsePlan:
    def test_valid_json_list_is_returned(self):
        from app.agents.planner_agent import _parse_plan
        tasks = [{"chapter_id": "c1", "estimated_duration_min": 60}]
        import json
        result = _parse_plan(json.dumps(tasks), [])
        assert result == tasks

    def test_json_object_with_tasks_key_is_unwrapped(self):
        from app.agents.planner_agent import _parse_plan
        import json
        tasks = [{"chapter_id": "c2", "estimated_duration_min": 45}]
        result = _parse_plan(json.dumps({"tasks": tasks}), [])
        assert result == tasks

    def test_invalid_json_falls_back_to_priority_sorted(self):
        from app.agents.planner_agent import _parse_plan
        pending = [
            {"id": "t1", "priority_score": 0.3, "estimated_duration_min": 60},
            {"id": "t2", "priority_score": 0.9, "estimated_duration_min": 90},
            {"id": "t3", "priority_score": 0.6, "estimated_duration_min": 45},
        ]
        result = _parse_plan("not valid json", pending)
        # Should be sorted by priority descending
        assert result[0]["id"] == "t2"
        assert result[1]["id"] == "t3"
        assert result[2]["id"] == "t1"

    def test_fallback_assigns_default_duration_when_missing(self):
        from app.agents.planner_agent import _parse_plan
        pending = [{"id": "t1", "priority_score": 0.5}]  # no estimated_duration_min
        result = _parse_plan("not json", pending)
        assert result[0]["estimated_duration_min"] == 90


# ===========================================================================
# Task F4 — Context enrichment tests (Requirements 11.4, 12.5)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tests for _get_top_mistake_chapters (with weakness_boost field)
# ---------------------------------------------------------------------------


class TestGetTopMistakeChapters:
    def _make_db(self, rows: list) -> MagicMock:
        result = _mock_result(rows)
        chain = MagicMock()
        chain.select.return_value = chain
        chain.execute.return_value = result
        db = MagicMock()
        db.table.return_value = chain
        return db

    def test_returns_empty_list_when_no_mistakes(self):
        from app.agents.planner_agent import _get_top_mistake_chapters
        db = self._make_db([])
        result = _get_top_mistake_chapters(db)
        assert result == []

    def test_aggregates_recurrence_counts_by_chapter(self):
        from app.agents.planner_agent import _get_top_mistake_chapters
        rows = [
            {"chapter_id": "c1", "recurrence_count": 3},
            {"chapter_id": "c1", "recurrence_count": 2},  # same chapter, should sum to 5
            {"chapter_id": "c2", "recurrence_count": 7},
        ]
        db = self._make_db(rows)
        result = _get_top_mistake_chapters(db)
        totals = {r["chapter_id"]: r["total_recurrence"] for r in result}
        assert totals["c1"] == 5
        assert totals["c2"] == 7

    def test_sorted_descending_by_total_recurrence(self):
        from app.agents.planner_agent import _get_top_mistake_chapters
        rows = [
            {"chapter_id": "c1", "recurrence_count": 2},
            {"chapter_id": "c2", "recurrence_count": 10},
            {"chapter_id": "c3", "recurrence_count": 5},
        ]
        db = self._make_db(rows)
        result = _get_top_mistake_chapters(db)
        totals = [r["total_recurrence"] for r in result]
        assert totals == sorted(totals, reverse=True)

    def test_respects_limit(self):
        from app.agents.planner_agent import _get_top_mistake_chapters
        rows = [{"chapter_id": f"c{i}", "recurrence_count": i} for i in range(1, 20)]
        db = self._make_db(rows)
        result = _get_top_mistake_chapters(db, limit=10)
        assert len(result) <= 10

    def test_weakness_boost_top_chapter_is_1(self):
        """The chapter with the highest recurrence must have weakness_boost == 1.0."""
        from app.agents.planner_agent import _get_top_mistake_chapters
        rows = [
            {"chapter_id": "best", "recurrence_count": 10},
            {"chapter_id": "other", "recurrence_count": 5},
        ]
        db = self._make_db(rows)
        result = _get_top_mistake_chapters(db)
        top = next(r for r in result if r["chapter_id"] == "best")
        assert top["weakness_boost"] == pytest.approx(1.0)

    def test_weakness_boost_proportional(self):
        """Lower-ranked chapters get a proportional boost."""
        from app.agents.planner_agent import _get_top_mistake_chapters
        rows = [
            {"chapter_id": "top", "recurrence_count": 10},
            {"chapter_id": "half", "recurrence_count": 5},
        ]
        db = self._make_db(rows)
        result = _get_top_mistake_chapters(db)
        boosts = {r["chapter_id"]: r["weakness_boost"] for r in result}
        assert boosts["half"] == pytest.approx(0.5)

    def test_ignores_rows_without_chapter_id(self):
        from app.agents.planner_agent import _get_top_mistake_chapters
        rows = [
            {"chapter_id": None, "recurrence_count": 100},  # should be ignored
            {"chapter_id": "c1", "recurrence_count": 3},
        ]
        db = self._make_db(rows)
        result = _get_top_mistake_chapters(db)
        chapter_ids = [r["chapter_id"] for r in result]
        assert None not in chapter_ids
        assert "c1" in chapter_ids


# ---------------------------------------------------------------------------
# Tests for _build_subject_weakness_map
# ---------------------------------------------------------------------------


class TestBuildSubjectWeaknessMap:
    def test_empty_summary_returns_empty_map(self):
        from app.agents.planner_agent import _build_subject_weakness_map
        result = _build_subject_weakness_map([])
        assert result == {}

    def test_100_percent_subject_has_zero_weakness(self):
        from app.agents.planner_agent import _build_subject_weakness_map
        summary = [{"subject_id": "s1", "avg_percentage": 100.0}]
        result = _build_subject_weakness_map(summary)
        assert result["s1"] == pytest.approx(0.0)

    def test_zero_percent_subject_has_max_weakness(self):
        from app.agents.planner_agent import _build_subject_weakness_map
        summary = [{"subject_id": "s1", "avg_percentage": 0.0}]
        result = _build_subject_weakness_map(summary)
        assert result["s1"] == pytest.approx(1.0)

    def test_50_percent_subject_has_half_weakness(self):
        from app.agents.planner_agent import _build_subject_weakness_map
        summary = [{"subject_id": "s1", "avg_percentage": 50.0}]
        result = _build_subject_weakness_map(summary)
        assert result["s1"] == pytest.approx(0.5)

    def test_multiple_subjects_mapped_independently(self):
        from app.agents.planner_agent import _build_subject_weakness_map
        summary = [
            {"subject_id": "s1", "avg_percentage": 80.0},
            {"subject_id": "s2", "avg_percentage": 40.0},
        ]
        result = _build_subject_weakness_map(summary)
        assert result["s1"] == pytest.approx(0.2)
        assert result["s2"] == pytest.approx(0.6)

    def test_skips_entries_with_missing_fields(self):
        from app.agents.planner_agent import _build_subject_weakness_map
        summary = [
            {"subject_id": None, "avg_percentage": 50.0},  # no subject_id
            {"subject_id": "s1", "avg_percentage": None},   # no avg_percentage
        ]
        result = _build_subject_weakness_map(summary)
        assert result == {}

    def test_result_clamped_to_0_1(self):
        """avg_percentage > 100 should not produce negative weakness."""
        from app.agents.planner_agent import _build_subject_weakness_map
        summary = [{"subject_id": "s1", "avg_percentage": 110.0}]
        result = _build_subject_weakness_map(summary)
        assert result["s1"] >= 0.0


# ---------------------------------------------------------------------------
# Tests for _enrich_task_weakness
# ---------------------------------------------------------------------------


class TestEnrichTaskWeakness:
    def test_no_enrichment_when_no_signals(self):
        """Tasks with no matching chapter or subject signal stay at base weakness."""
        from app.agents.planner_agent import _enrich_task_weakness
        tasks = [
            {"id": "t1", "chapter_id": "c99", "subject_id": "s99", "weakness_score": 0.5},
        ]
        result = _enrich_task_weakness(tasks, [], {})
        assert result[0]["weakness_score"] == pytest.approx(0.5)

    def test_does_not_mutate_input_tasks(self):
        from app.agents.planner_agent import _enrich_task_weakness
        original = {"id": "t1", "chapter_id": "c1", "subject_id": "s1", "weakness_score": 0.4}
        tasks = [original]
        top_mistakes = [{"chapter_id": "c1", "total_recurrence": 5, "weakness_boost": 1.0}]
        _enrich_task_weakness(tasks, top_mistakes, {})
        # Original must be unmodified
        assert original["weakness_score"] == 0.4

    def test_mistake_boost_increases_weakness(self):
        from app.agents.planner_agent import _enrich_task_weakness
        tasks = [{"id": "t1", "chapter_id": "c1", "subject_id": None, "weakness_score": 0.3}]
        top_mistakes = [{"chapter_id": "c1", "total_recurrence": 10, "weakness_boost": 1.0}]
        result = _enrich_task_weakness(tasks, top_mistakes, {}, mistake_weight=0.3)
        # 0.3 + 0.3*1.0 = 0.6
        assert result[0]["weakness_score"] == pytest.approx(0.6)

    def test_test_weakness_increases_weakness(self):
        from app.agents.planner_agent import _enrich_task_weakness
        tasks = [{"id": "t1", "chapter_id": None, "subject_id": "s1", "weakness_score": 0.4}]
        subject_map = {"s1": 0.5}
        result = _enrich_task_weakness(tasks, [], subject_map, test_weight=0.2)
        # 0.4 + 0.2*0.5 = 0.5
        assert result[0]["weakness_score"] == pytest.approx(0.5)

    def test_both_signals_combine(self):
        from app.agents.planner_agent import _enrich_task_weakness
        tasks = [{"id": "t1", "chapter_id": "c1", "subject_id": "s1", "weakness_score": 0.2}]
        top_mistakes = [{"chapter_id": "c1", "total_recurrence": 10, "weakness_boost": 0.8}]
        subject_map = {"s1": 0.6}
        result = _enrich_task_weakness(
            tasks, top_mistakes, subject_map, mistake_weight=0.3, test_weight=0.2
        )
        expected = pytest.approx(0.2 + 0.3 * 0.8 + 0.2 * 0.6, abs=1e-5)
        assert result[0]["weakness_score"] == expected

    def test_enriched_weakness_clamped_to_1(self):
        """Enrichment must not push weakness_score above 1.0."""
        from app.agents.planner_agent import _enrich_task_weakness
        tasks = [{"id": "t1", "chapter_id": "c1", "subject_id": "s1", "weakness_score": 0.9}]
        top_mistakes = [{"chapter_id": "c1", "total_recurrence": 10, "weakness_boost": 1.0}]
        subject_map = {"s1": 1.0}
        result = _enrich_task_weakness(tasks, top_mistakes, subject_map)
        assert result[0]["weakness_score"] <= 1.0

    def test_priority_score_recomputed_after_enrichment(self):
        """After enrichment the priority_score must reflect the enriched weakness."""
        from app.agents.planner_agent import _enrich_task_weakness
        from app.priority import PriorityFactors, clamp, compute_priority_score
        tasks = [
            {
                "id": "t1",
                "chapter_id": "c1",
                "subject_id": None,
                "weakness_score": 0.2,
                "deadline_pressure": 0.5,
                "board_weightage": 0.5,
                "backlog_score": 0.5,
                "revision_due_score": 0.5,
                "priority_score": 0.0,  # stale value
            }
        ]
        top_mistakes = [{"chapter_id": "c1", "total_recurrence": 10, "weakness_boost": 1.0}]
        result = _enrich_task_weakness(tasks, top_mistakes, {}, mistake_weight=0.3)
        enriched_weakness = clamp(0.2 + 0.3 * 1.0)  # 0.5
        expected_score = compute_priority_score(
            PriorityFactors(
                weakness_score=enriched_weakness,
                deadline_pressure=0.5,
                board_weightage=0.5,
                backlog_score=0.5,
                revision_due_score=0.5,
            )
        )
        assert result[0]["priority_score"] == pytest.approx(expected_score)

    def test_tasks_without_chapter_id_unaffected_by_mistake_boost(self):
        from app.agents.planner_agent import _enrich_task_weakness
        tasks = [{"id": "t1", "chapter_id": None, "subject_id": None, "weakness_score": 0.4}]
        top_mistakes = [{"chapter_id": "c1", "total_recurrence": 10, "weakness_boost": 1.0}]
        result = _enrich_task_weakness(tasks, top_mistakes, {})
        assert result[0]["weakness_score"] == pytest.approx(0.4)

    def test_returns_correct_number_of_tasks(self):
        from app.agents.planner_agent import _enrich_task_weakness
        tasks = [
            {"id": f"t{i}", "chapter_id": f"c{i}", "subject_id": None, "weakness_score": 0.3}
            for i in range(5)
        ]
        result = _enrich_task_weakness(tasks, [], {})
        assert len(result) == 5


# ---------------------------------------------------------------------------
# Tests for run_nightly_plan with enrichment wired in
# ---------------------------------------------------------------------------


class TestRunNightlyPlanWithEnrichment:
    @pytest.mark.asyncio
    async def test_enriched_tasks_are_passed_to_ask_tillu(self):
        """ask_tillu context['tasks'] must be the enriched list, not the raw DB list."""
        raw_task = {
            "id": "t1",
            "chapter_id": "c1",
            "subject_id": "s1",
            "weakness_score": 0.2,
            "estimated_duration_min": 60,
            "status": "pending",
        }
        mistakes_rows = [{"chapter_id": "c1", "recurrence_count": 10}]
        tests_rows = [{"subject_id": "s1", "percentage": 40.0}]  # low → high weakness

        db = _make_db_mock(
            pending_tasks=[raw_task],
            mistakes=mistakes_rows,
            tests=tests_rows,
        )

        captured_context: list[dict] = []

        async def fake_ask_tillu(user_message, context):
            captured_context.append(context)
            return "[]"

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch("app.agents.planner_agent.ask_tillu", side_effect=fake_ask_tillu),
            patch(
                "app.agents.planner_agent.create_task",
                return_value={"id": "created", "estimated_duration_min": 60},
            ),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        assert len(captured_context) == 1
        ctx_tasks = captured_context[0]["tasks"]
        assert len(ctx_tasks) == 1
        # Enriched weakness must be strictly greater than the raw 0.2 value
        assert ctx_tasks[0]["weakness_score"] > 0.2, (
            "Expected weakness_score to be boosted by mistake + test signals"
        )

    @pytest.mark.asyncio
    async def test_test_summary_included_in_context(self):
        """context['test_summary'] must contain per-subject avg_percentage."""
        tests_rows = [
            {"subject_id": "s1", "percentage": 60.0},
            {"subject_id": "s1", "percentage": 80.0},
        ]
        db = _make_db_mock(tests=tests_rows)

        captured_context: list[dict] = []

        async def fake_ask_tillu(user_message, context):
            captured_context.append(context)
            return "[]"

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch("app.agents.planner_agent.ask_tillu", side_effect=fake_ask_tillu),
            patch("app.agents.planner_agent._parse_plan", return_value=[]),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        assert len(captured_context) == 1
        test_summary = captured_context[0]["test_summary"]
        assert len(test_summary) == 1
        assert test_summary[0]["subject_id"] == "s1"
        assert test_summary[0]["avg_percentage"] == pytest.approx(70.0)

    @pytest.mark.asyncio
    async def test_weak_chapters_includes_weakness_boost(self):
        """context['weak_chapters'] entries must have a 'weakness_boost' key."""
        mistakes_rows = [
            {"chapter_id": "c1", "recurrence_count": 10},
            {"chapter_id": "c2", "recurrence_count": 5},
        ]
        db = _make_db_mock(mistakes=mistakes_rows)

        captured_context: list[dict] = []

        async def fake_ask_tillu(user_message, context):
            captured_context.append(context)
            return "[]"

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch("app.agents.planner_agent.ask_tillu", side_effect=fake_ask_tillu),
            patch("app.agents.planner_agent._parse_plan", return_value=[]),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        weak_chapters = captured_context[0]["weak_chapters"]
        assert all("weakness_boost" in ch for ch in weak_chapters)
        # Top chapter should have boost 1.0
        assert weak_chapters[0]["weakness_boost"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_enriched_weakness_passed_to_create_task(self):
        """The enriched weakness_score must appear in the create_task payload."""
        raw_task = {
            "id": "t1",
            "chapter_id": "c1",
            "subject_id": None,
            "weakness_score": 0.1,  # low base
            "estimated_duration_min": 60,
            "status": "pending",
        }
        mistakes_rows = [{"chapter_id": "c1", "recurrence_count": 10}]
        db = _make_db_mock(pending_tasks=[raw_task], mistakes=mistakes_rows)

        inserted_payloads: list[dict] = []

        def fake_create(payload):
            inserted_payloads.append(dict(payload))
            return {"id": "new", **payload}

        with (
            patch("app.agents.planner_agent.get_client", return_value=db),
            patch(
                "app.agents.planner_agent.get_sleep_window",
                new_callable=AsyncMock,
                return_value=("23:00", "06:00"),
            ),
            patch(
                "app.agents.planner_agent.ask_tillu",
                new_callable=AsyncMock,
                return_value="[]",
            ),
            patch(
                "app.agents.planner_agent._parse_plan",
                # Return the enriched task directly; planner uses it as proposed
                side_effect=lambda response, tasks: tasks,
            ),
            patch("app.agents.planner_agent.create_task", side_effect=fake_create),
            patch("app.agents.planner_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.planner_agent import run_nightly_plan
            await run_nightly_plan()

        assert len(inserted_payloads) == 1
        # weakness_score in the payload must be the enriched value > 0.1
        assert inserted_payloads[0].get("weakness_score", 0) > 0.1
