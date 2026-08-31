"""Unit tests for backend/app/scheduler.py.

Covers:
- start_scheduler registers exactly 3 jobs (nightly_plan, reminder_check,
  missed_task_check)
- _safe_run catches exceptions from a failing coroutine and logs them without
  re-raising
- _safe_run awaits (calls) the supplied job function
- stop_scheduler shuts down the scheduler when it is running

All tests run without an APScheduler event loop by patching _scheduler where
needed or by working with a freshly constructed scheduler instance.

Implements Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fresh_scheduler():
    """Return a new AsyncIOScheduler that hasn't been started."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    return AsyncIOScheduler()


# ---------------------------------------------------------------------------
# _safe_run
# ---------------------------------------------------------------------------


class TestSafeRun:
    """Tests for the _safe_run error-wrapper coroutine."""

    @pytest.mark.asyncio
    async def test_awaits_job_function(self):
        """_safe_run must await (call) the supplied coroutine function."""
        from app.scheduler import _safe_run

        called = []

        async def my_job():
            called.append(True)

        await _safe_run(my_job, "test_job")

        assert called == [True], "_safe_run did not await the job function"

    @pytest.mark.asyncio
    async def test_catches_exception_without_raising(self):
        """_safe_run must swallow any exception raised by the job function."""
        from app.scheduler import _safe_run

        async def failing_job():
            raise ValueError("boom")

        # Must not raise
        await _safe_run(failing_job, "failing_test_job")

    @pytest.mark.asyncio
    async def test_logs_exception_with_job_name(self, caplog):
        """_safe_run must log an error containing the job name when the job fails."""
        from app.scheduler import _safe_run

        async def broken_job():
            raise RuntimeError("scheduler error")

        with caplog.at_level(logging.ERROR, logger="app.scheduler"):
            await _safe_run(broken_job, "my_broken_job")

        assert any(
            "my_broken_job" in record.message for record in caplog.records
        ), "Expected job name in error log"

    @pytest.mark.asyncio
    async def test_succeeds_silently_on_normal_job(self, caplog):
        """_safe_run must not emit error logs when the job succeeds."""
        from app.scheduler import _safe_run

        async def good_job():
            pass  # no-op

        with caplog.at_level(logging.ERROR, logger="app.scheduler"):
            await _safe_run(good_job, "good_job")

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_records == [], "No error logs expected for a succeeding job"


# ---------------------------------------------------------------------------
# start_scheduler
# ---------------------------------------------------------------------------


class TestStartScheduler:
    """Tests for start_scheduler job registration."""

    @pytest.mark.asyncio
    async def test_registers_exactly_three_jobs(self):
        """start_scheduler must register nightly_plan, reminder_check, and
        missed_task_check — no more, no fewer."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        fresh = AsyncIOScheduler()

        # Patch the module-level _scheduler so we can inspect it afterwards,
        # and patch out the agent imports to avoid real Supabase I/O.
        with (
            patch("app.scheduler._scheduler", fresh),
            patch("app.agents.planner_agent.run_nightly_plan", new=AsyncMock()),
            patch("app.agents.planner_agent.check_missed_tasks", new=AsyncMock()),
            patch("app.agents.reminder_agent.check_reminders", new=AsyncMock()),
        ):
            from app.scheduler import start_scheduler

            await start_scheduler()

            job_ids = {job.id for job in fresh.get_jobs()}
            assert job_ids == {
                "nightly_plan",
                "reminder_check",
                "missed_task_check",
            }, f"Expected 3 jobs, got: {job_ids}"

            # Cleanup
            fresh.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_nightly_plan_uses_cron_trigger(self):
        """nightly_plan job must use a CronTrigger."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        fresh = AsyncIOScheduler()

        with (
            patch("app.scheduler._scheduler", fresh),
            patch("app.agents.planner_agent.run_nightly_plan", new=AsyncMock()),
            patch("app.agents.planner_agent.check_missed_tasks", new=AsyncMock()),
            patch("app.agents.reminder_agent.check_reminders", new=AsyncMock()),
        ):
            from app.scheduler import start_scheduler

            await start_scheduler()

            job = fresh.get_job("nightly_plan")
            assert job is not None
            assert isinstance(
                job.trigger, CronTrigger
            ), "nightly_plan must use CronTrigger"

            fresh.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_interval_jobs_use_interval_trigger(self):
        """reminder_check and missed_task_check must use IntervalTrigger."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        fresh = AsyncIOScheduler()

        with (
            patch("app.scheduler._scheduler", fresh),
            patch("app.agents.planner_agent.run_nightly_plan", new=AsyncMock()),
            patch("app.agents.planner_agent.check_missed_tasks", new=AsyncMock()),
            patch("app.agents.reminder_agent.check_reminders", new=AsyncMock()),
        ):
            from app.scheduler import start_scheduler

            await start_scheduler()

            reminder_job = fresh.get_job("reminder_check")
            missed_job = fresh.get_job("missed_task_check")

            assert isinstance(reminder_job.trigger, IntervalTrigger)
            assert isinstance(missed_job.trigger, IntervalTrigger)

            fresh.shutdown(wait=False)


# ---------------------------------------------------------------------------
# stop_scheduler
# ---------------------------------------------------------------------------


class TestStopScheduler:
    """Tests for stop_scheduler teardown behaviour."""

    @pytest.mark.asyncio
    async def test_shuts_down_running_scheduler(self):
        """stop_scheduler must call shutdown on a running scheduler."""
        mock_sched = MagicMock()
        mock_sched.running = True

        with patch("app.scheduler._scheduler", mock_sched):
            from app.scheduler import stop_scheduler

            await stop_scheduler()

        mock_sched.shutdown.assert_called_once_with(wait=False)

    @pytest.mark.asyncio
    async def test_does_not_shutdown_stopped_scheduler(self):
        """stop_scheduler must not call shutdown when the scheduler is not running."""
        mock_sched = MagicMock()
        mock_sched.running = False

        with patch("app.scheduler._scheduler", mock_sched):
            from app.scheduler import stop_scheduler

            await stop_scheduler()

        mock_sched.shutdown.assert_not_called()
