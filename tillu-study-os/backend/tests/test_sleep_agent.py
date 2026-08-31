"""Tests for backend/app/agents/sleep_agent.py.

Covers:
  1. get_sleep_window() returns DB values when a sleep_log exists for today.
  2. get_sleep_window() returns config defaults when no sleep_log exists for today,
     and emits a WARNING.
  3. sleep_window_overlaps() for normal (same-day) and overnight cases.

All tests run without a live Supabase connection — the DB client is patched.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.agents.sleep_agent import get_sleep_window, sleep_window_overlaps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_mock(rows: list[dict]) -> MagicMock:
    """Return a mock Supabase client whose sleep_logs query returns *rows*."""
    execute_mock = MagicMock()
    execute_mock.data = rows

    chain = MagicMock()
    chain.execute.return_value = execute_mock
    # Every chained call (select, eq, order, limit) returns the same chain mock
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain

    db_mock = MagicMock()
    db_mock.table.return_value = chain
    return db_mock


# ---------------------------------------------------------------------------
# get_sleep_window() — DB record found
# ---------------------------------------------------------------------------

class TestGetSleepWindowWithRecord:
    @pytest.mark.asyncio
    async def test_returns_db_sleep_start_and_end(self):
        """When a sleep_log exists for today, get_sleep_window returns its values."""
        db_mock = _make_db_mock([{"sleep_start": "22:30", "sleep_end": "06:00"}])

        with patch("app.agents.sleep_agent.get_client", return_value=db_mock):
            start, end = await get_sleep_window()

        assert start == "22:30"
        assert end == "06:00"

    @pytest.mark.asyncio
    async def test_returns_most_recent_entry(self):
        """Only the first row is used (the query already orders desc + limit 1)."""
        db_mock = _make_db_mock([{"sleep_start": "23:15", "sleep_end": "07:00"}])

        with patch("app.agents.sleep_agent.get_client", return_value=db_mock):
            start, end = await get_sleep_window()

        assert start == "23:15"
        assert end == "07:00"

    @pytest.mark.asyncio
    async def test_normalises_hh_mm_ss_format(self):
        """Postgres TIME values may arrive as HH:MM:SS — they must be trimmed to HH:MM."""
        db_mock = _make_db_mock([{"sleep_start": "23:00:00", "sleep_end": "06:00:00"}])

        with patch("app.agents.sleep_agent.get_client", return_value=db_mock):
            start, end = await get_sleep_window()

        assert start == "23:00"
        assert end == "06:00"


# ---------------------------------------------------------------------------
# get_sleep_window() — No record for today (default fallback)
# ---------------------------------------------------------------------------

class TestGetSleepWindowDefaultFallback:
    @pytest.mark.asyncio
    async def test_returns_default_sleep_start(self):
        """Falls back to settings.default_sleep_start when no log exists for today."""
        db_mock = _make_db_mock([])  # empty result

        with patch("app.agents.sleep_agent.get_client", return_value=db_mock):
            from app.config import settings
            start, end = await get_sleep_window()

        assert start == settings.default_sleep_start

    @pytest.mark.asyncio
    async def test_returns_default_sleep_end(self):
        """Falls back to settings.default_sleep_end when no log exists for today."""
        db_mock = _make_db_mock([])

        with patch("app.agents.sleep_agent.get_client", return_value=db_mock):
            from app.config import settings
            start, end = await get_sleep_window()

        assert end == settings.default_sleep_end

    @pytest.mark.asyncio
    async def test_logs_warning_when_using_defaults(self, caplog):
        """A WARNING must be logged when the default window is applied."""
        import logging
        db_mock = _make_db_mock([])

        with patch("app.agents.sleep_agent.get_client", return_value=db_mock):
            with caplog.at_level(logging.WARNING, logger="app.agents.sleep_agent"):
                await get_sleep_window()

        assert any("default" in record.message.lower() for record in caplog.records)


# ---------------------------------------------------------------------------
# sleep_window_overlaps() — same-day (normal) cases
# ---------------------------------------------------------------------------

class TestSleepWindowOverlapsSameDay:
    def test_task_fully_before_sleep_does_not_overlap(self):
        # Sleep 22:00–06:00 (overnight), task 08:00–10:00
        assert sleep_window_overlaps("08:00", "10:00", "22:00", "06:00") is False

    def test_task_fully_inside_sleep_overlaps(self):
        # Sleep 23:00–07:00, task 01:00–03:00 (clearly inside overnight window)
        assert sleep_window_overlaps("01:00", "03:00", "23:00", "07:00") is True

    def test_task_starts_during_sleep_overlaps(self):
        # Sleep 14:00–16:00, task 15:00–17:00 (starts inside)
        assert sleep_window_overlaps("15:00", "17:00", "14:00", "16:00") is True

    def test_task_ends_during_sleep_overlaps(self):
        # Sleep 14:00–16:00, task 13:00–15:00 (ends inside)
        assert sleep_window_overlaps("13:00", "15:00", "14:00", "16:00") is True

    def test_task_fully_after_sleep_does_not_overlap(self):
        # Sleep 14:00–16:00, task 17:00–18:00 (entirely after)
        assert sleep_window_overlaps("17:00", "18:00", "14:00", "16:00") is False

    def test_task_exactly_adjacent_before_sleep_does_not_overlap(self):
        # Sleep starts 14:00, task ends 14:00 — touching but not overlapping
        assert sleep_window_overlaps("12:00", "14:00", "14:00", "16:00") is False

    def test_task_exactly_adjacent_after_sleep_does_not_overlap(self):
        # Sleep ends 16:00, task starts 16:00 — touching but not overlapping
        assert sleep_window_overlaps("16:00", "18:00", "14:00", "16:00") is False

    def test_task_fully_wraps_sleep_overlaps(self):
        # Task 13:00–17:00 completely contains sleep 14:00–16:00
        assert sleep_window_overlaps("13:00", "17:00", "14:00", "16:00") is True


# ---------------------------------------------------------------------------
# sleep_window_overlaps() — overnight cases
# ---------------------------------------------------------------------------

class TestSleepWindowOverlapsOvernight:
    def test_task_during_waking_hours_does_not_overlap_overnight_sleep(self):
        # Sleep 23:00–06:00 (overnight), task 10:00–12:00
        assert sleep_window_overlaps("10:00", "12:00", "23:00", "06:00") is False

    def test_task_starts_before_midnight_in_overnight_sleep_overlaps(self):
        # Sleep 23:00–06:00, task 23:30–00:30 (straddles midnight, in sleep window)
        assert sleep_window_overlaps("23:30", "00:30", "23:00", "06:00") is True

    def test_task_early_morning_inside_overnight_sleep_overlaps(self):
        # Sleep 23:00–06:00, task 04:00–05:00 (well inside sleep window)
        assert sleep_window_overlaps("04:00", "05:00", "23:00", "06:00") is True

    def test_task_after_overnight_sleep_end_does_not_overlap(self):
        # Sleep 23:00–06:00, task 07:00–09:00 (after sleep ends)
        assert sleep_window_overlaps("07:00", "09:00", "23:00", "06:00") is False

    def test_task_starting_exactly_at_sleep_end_does_not_overlap(self):
        # Sleep 23:00–06:00, task starts exactly at 06:00
        assert sleep_window_overlaps("06:00", "07:00", "23:00", "06:00") is False

    def test_overnight_task_overlaps_overnight_sleep(self):
        # Both the task and sleep are overnight
        # Sleep 23:00–06:00, task 01:00–03:00
        assert sleep_window_overlaps("01:00", "03:00", "23:00", "06:00") is True
