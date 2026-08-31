"""APScheduler background jobs for Tillu AI Study OS.

Three recurring jobs:
  1. nightly_plan      — CronTrigger at settings.scheduler_nightly_hour:scheduler_nightly_minute
  2. reminder_check    — IntervalTrigger every 5 minutes
  3. missed_task_check — IntervalTrigger every 30 minutes

Uses AsyncIOScheduler so jobs run on the same event loop as FastAPI.
_safe_run() wraps each job: catches all exceptions, logs with traceback, never re-raises.
APScheduler reschedules automatically after a job error.

Implements Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""
import logging
import traceback

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level scheduler instance — shared across start/stop calls.
_scheduler = AsyncIOScheduler()


async def _safe_run(job_fn, job_name: str) -> None:
    """Wrap a job coroutine: catch all exceptions, log with traceback, never re-raise.

    APScheduler reschedules automatically regardless of job outcome, so we
    only need to ensure unhandled exceptions are surfaced in the log without
    propagating to the scheduler event loop.

    Args:
        job_fn: An async callable (coroutine function) to invoke.
        job_name: Human-readable name used in the error log message.
    """
    try:
        await job_fn()
    except Exception:
        logger.error(
            "Scheduler job '%s' failed:\n%s", job_name, traceback.format_exc()
        )
    # APScheduler reschedules automatically — no action needed here


async def start_scheduler() -> None:
    """Register all three jobs and start the AsyncIOScheduler.

    Imports the job coroutines lazily (inside the function) to avoid circular
    imports at module load time.  Safe to call multiple times — APScheduler
    replaces existing jobs when replace_existing=True.
    """
    from app.agents.planner_agent import run_nightly_plan, check_missed_tasks
    from app.agents.reminder_agent import check_reminders

    _scheduler.add_job(
        lambda: _safe_run(run_nightly_plan, "nightly_plan"),
        CronTrigger(
            hour=settings.scheduler_nightly_hour,
            minute=settings.scheduler_nightly_minute,
        ),
        id="nightly_plan",
        replace_existing=True,
    )
    _scheduler.add_job(
        lambda: _safe_run(check_reminders, "reminder_check"),
        IntervalTrigger(minutes=5),
        id="reminder_check",
        replace_existing=True,
    )
    _scheduler.add_job(
        lambda: _safe_run(check_missed_tasks, "missed_task_check"),
        IntervalTrigger(minutes=30),
        id="missed_task_check",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — nightly_plan at %02d:%02d, "
        "reminder_check every 5 min, missed_task_check every 30 min",
        settings.scheduler_nightly_hour,
        settings.scheduler_nightly_minute,
    )


async def stop_scheduler() -> None:
    """Shut down the scheduler gracefully (don't wait for running jobs)."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
