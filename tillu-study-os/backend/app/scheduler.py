"""APScheduler background job scheduler.

Stub implementation — full scheduler will be wired in task 9.9.
Registers three recurring jobs:
  - nightly plan (CronTrigger)
  - reminder check (IntervalTrigger every 5 min)
  - missed task check (IntervalTrigger every 30 min)
"""

import logging
import traceback

logger = logging.getLogger(__name__)

# Will be replaced with AsyncIOScheduler in task 9.9.
_scheduler = None


async def _safe_run(job_fn, job_name: str) -> None:
    """Wrap a job coroutine so exceptions are logged but do not crash the scheduler."""
    try:
        await job_fn()
    except Exception:
        logger.error("Scheduler job %s failed:\n%s", job_name, traceback.format_exc())


async def start_scheduler() -> None:
    """Start background scheduler.  (Stub — no jobs registered yet.)"""
    logger.info("Scheduler started (stub)")


async def stop_scheduler() -> None:
    """Stop background scheduler."""
    logger.info("Scheduler stopped (stub)")
