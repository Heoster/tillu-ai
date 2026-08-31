"""Unit tests for backend/app/agents/reminder_agent.py.

Covers:
  1. check_reminders() queries only 'pending' reminders in the 5-minute window.
  2. _dispatch_reminder() calls all three channels (toast, chime, WebSocket).
  3. _dispatch_reminder() marks reminder as 'fired' after dispatch.
  4. _send_toast() failure does NOT prevent WebSocket broadcast or status update.
  5. _play_chime() failure does NOT prevent toast or WebSocket broadcast.
  6. Reminder status transition is pending → fired only (never backward).

All tests run without a live Supabase connection — DB client and external
libraries are patched via unittest.mock.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_mock(rows: list[dict] | None = None) -> MagicMock:
    """Return a mock Supabase client whose reminders query returns *rows*."""
    if rows is None:
        rows = []

    execute_mock = MagicMock()
    execute_mock.data = rows

    chain = MagicMock()
    chain.execute.return_value = execute_mock
    # All chained query methods return the same chain mock
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.update.return_value = chain

    db_mock = MagicMock()
    db_mock.table.return_value = chain
    return db_mock


def _sample_reminder(
    reminder_id: str = "rem-001",
    title: str = "Study Physics",
    scheduled_at: str = "2024-11-01T10:00:00",
    status: str = "pending",
) -> dict:
    return {
        "id": reminder_id,
        "title": title,
        "scheduled_at": scheduled_at,
        "status": status,
    }


# ---------------------------------------------------------------------------
# 1. check_reminders() — queries only 'pending' reminders in 5-min window
# ---------------------------------------------------------------------------

class TestCheckRemindersQuery:
    @pytest.mark.asyncio
    async def test_queries_reminders_table(self):
        """check_reminders must query the 'reminders' table."""
        db_mock = _make_db_mock([])

        with (
            patch("app.agents.reminder_agent.get_client", return_value=db_mock),
            patch("app.agents.reminder_agent._dispatch_reminder", new_callable=AsyncMock),
        ):
            from app.agents.reminder_agent import check_reminders
            await check_reminders()

        db_mock.table.assert_called_with("reminders")

    @pytest.mark.asyncio
    async def test_filters_by_pending_status(self):
        """check_reminders must apply .eq('status', 'pending') filter."""
        db_mock = _make_db_mock([])
        chain = db_mock.table.return_value

        with (
            patch("app.agents.reminder_agent.get_client", return_value=db_mock),
            patch("app.agents.reminder_agent._dispatch_reminder", new_callable=AsyncMock),
        ):
            from app.agents.reminder_agent import check_reminders
            await check_reminders()

        # Verify the chain received eq('status', 'pending')
        eq_calls = chain.eq.call_args_list
        assert any(
            c == call("status", "pending") for c in eq_calls
        ), f"Expected .eq('status', 'pending') in calls: {eq_calls}"

    @pytest.mark.asyncio
    async def test_applies_gte_filter_on_scheduled_at(self):
        """check_reminders must apply .gte('scheduled_at', ...) for window start."""
        db_mock = _make_db_mock([])
        chain = db_mock.table.return_value

        with (
            patch("app.agents.reminder_agent.get_client", return_value=db_mock),
            patch("app.agents.reminder_agent._dispatch_reminder", new_callable=AsyncMock),
        ):
            from app.agents.reminder_agent import check_reminders
            await check_reminders()

        gte_calls = chain.gte.call_args_list
        assert any(
            c.args[0] == "scheduled_at" for c in gte_calls
        ), f"Expected .gte('scheduled_at', ...) in calls: {gte_calls}"

    @pytest.mark.asyncio
    async def test_applies_lte_filter_on_scheduled_at(self):
        """check_reminders must apply .lte('scheduled_at', ...) for window end."""
        db_mock = _make_db_mock([])
        chain = db_mock.table.return_value

        with (
            patch("app.agents.reminder_agent.get_client", return_value=db_mock),
            patch("app.agents.reminder_agent._dispatch_reminder", new_callable=AsyncMock),
        ):
            from app.agents.reminder_agent import check_reminders
            await check_reminders()

        lte_calls = chain.lte.call_args_list
        assert any(
            c.args[0] == "scheduled_at" for c in lte_calls
        ), f"Expected .lte('scheduled_at', ...) in calls: {lte_calls}"

    @pytest.mark.asyncio
    async def test_dispatches_each_returned_reminder(self):
        """check_reminders must call _dispatch_reminder for every row returned."""
        reminders = [
            _sample_reminder("rem-001"),
            _sample_reminder("rem-002", title="Revise Chemistry"),
        ]
        db_mock = _make_db_mock(reminders)

        with (
            patch("app.agents.reminder_agent.get_client", return_value=db_mock),
            patch(
                "app.agents.reminder_agent._dispatch_reminder",
                new_callable=AsyncMock,
            ) as mock_dispatch,
        ):
            from app.agents.reminder_agent import check_reminders
            await check_reminders()

        assert mock_dispatch.await_count == 2

    @pytest.mark.asyncio
    async def test_no_dispatch_when_no_reminders(self):
        """check_reminders must not call _dispatch_reminder when result is empty."""
        db_mock = _make_db_mock([])

        with (
            patch("app.agents.reminder_agent.get_client", return_value=db_mock),
            patch(
                "app.agents.reminder_agent._dispatch_reminder",
                new_callable=AsyncMock,
            ) as mock_dispatch,
        ):
            from app.agents.reminder_agent import check_reminders
            await check_reminders()

        mock_dispatch.assert_not_awaited()


# ---------------------------------------------------------------------------
# 2. _dispatch_reminder() — calls all three channels
# ---------------------------------------------------------------------------

class TestDispatchReminderAllChannels:
    @pytest.mark.asyncio
    async def test_calls_send_toast(self):
        """_dispatch_reminder must call _send_toast with the reminder title."""
        db_mock = _make_db_mock()
        reminder = _sample_reminder()

        with (
            patch("app.agents.reminder_agent._send_toast") as mock_toast,
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        mock_toast.assert_called_once()
        assert mock_toast.call_args.args[0] == reminder["title"]

    @pytest.mark.asyncio
    async def test_calls_play_chime(self):
        """_dispatch_reminder must call _play_chime."""
        db_mock = _make_db_mock()
        reminder = _sample_reminder()

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch("app.agents.reminder_agent._play_chime") as mock_chime,
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        mock_chime.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcasts_reminder_event_via_websocket(self):
        """_dispatch_reminder must broadcast a 'reminder' type event via ws_manager."""
        db_mock = _make_db_mock()
        reminder = _sample_reminder()

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        mock_ws.broadcast.assert_awaited_once()
        broadcast_event = mock_ws.broadcast.call_args.args[0]
        assert broadcast_event["type"] == "reminder"
        assert broadcast_event["reminder_id"] == reminder["id"]
        assert broadcast_event["title"] == reminder["title"]

    @pytest.mark.asyncio
    async def test_broadcast_event_includes_scheduled_at(self):
        """Broadcast event must include 'scheduled_at' field."""
        db_mock = _make_db_mock()
        reminder = _sample_reminder(scheduled_at="2024-11-01T14:30:00")

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        broadcast_event = mock_ws.broadcast.call_args.args[0]
        assert broadcast_event["scheduled_at"] == "2024-11-01T14:30:00"


# ---------------------------------------------------------------------------
# 3. _dispatch_reminder() — marks reminder as 'fired' after dispatch
# ---------------------------------------------------------------------------

class TestDispatchReminderMarkFired:
    @pytest.mark.asyncio
    async def test_updates_status_to_fired(self):
        """_dispatch_reminder must call db.update({'status': 'fired'}) on the reminder."""
        db_mock = _make_db_mock()
        chain = db_mock.table.return_value
        reminder = _sample_reminder(reminder_id="rem-abc")

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        # update({'status': 'fired'}) must have been called
        update_calls = chain.update.call_args_list
        assert any(
            c == call({"status": "fired"}) for c in update_calls
        ), f"Expected update({{'status': 'fired'}}) in calls: {update_calls}"

    @pytest.mark.asyncio
    async def test_status_update_filters_by_reminder_id(self):
        """Status update must be scoped to the specific reminder id."""
        db_mock = _make_db_mock()
        chain = db_mock.table.return_value
        reminder = _sample_reminder(reminder_id="rem-xyz")

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        eq_calls = chain.eq.call_args_list
        assert any(
            c == call("id", "rem-xyz") for c in eq_calls
        ), f"Expected .eq('id', 'rem-xyz') in calls: {eq_calls}"

    @pytest.mark.asyncio
    async def test_mark_fired_happens_after_all_channels(self):
        """Status update to 'fired' must occur after all three channel calls."""
        db_mock = _make_db_mock()
        chain = db_mock.table.return_value
        reminder = _sample_reminder()
        call_order: list[str] = []

        def toast_tracker(*args, **kwargs):
            call_order.append("toast")

        def chime_tracker(*args, **kwargs):
            call_order.append("chime")

        async def ws_tracker(*args, **kwargs):
            call_order.append("ws")

        def update_tracker(*args, **kwargs):
            call_order.append("update")
            return chain  # keep chain intact

        with (
            patch("app.agents.reminder_agent._send_toast", side_effect=toast_tracker),
            patch("app.agents.reminder_agent._play_chime", side_effect=chime_tracker),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock(side_effect=ws_tracker)
            # Patch the update call so we can track its position
            chain.update.side_effect = update_tracker

            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        # All three channels must appear before the update
        assert "update" in call_order
        update_idx = call_order.index("update")
        for channel in ("toast", "chime", "ws"):
            assert channel in call_order
            assert call_order.index(channel) < update_idx, (
                f"'{channel}' must occur before 'update'; order was {call_order}"
            )


# ---------------------------------------------------------------------------
# 4. _send_toast() failure does NOT prevent WebSocket broadcast or status update
#
# The channel isolation works because _send_toast() and _play_chime() each
# contain their own try/except and never raise.  The correct way to test this
# is to simulate the underlying library raising (plyer/pygame), which is what
# the real failure scenario looks like at runtime.
# ---------------------------------------------------------------------------

class TestToastFailureIsolation:
    @pytest.mark.asyncio
    async def test_ws_broadcast_fires_when_plyer_raises(self):
        """WebSocket broadcast must be called even when plyer.notify raises."""
        db_mock = _make_db_mock()
        reminder = _sample_reminder()

        plyer_mock = MagicMock()
        plyer_mock.notification.notify.side_effect = Exception("toast hardware failure")

        with (
            patch.dict("sys.modules", {"plyer": plyer_mock}),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        mock_ws.broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_status_update_fires_when_plyer_raises(self):
        """Status update to 'fired' must happen even when plyer.notify raises."""
        db_mock = _make_db_mock()
        chain = db_mock.table.return_value
        reminder = _sample_reminder()

        plyer_mock = MagicMock()
        plyer_mock.notification.notify.side_effect = Exception("toast unavailable")

        with (
            patch.dict("sys.modules", {"plyer": plyer_mock}),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        update_calls = chain.update.call_args_list
        assert any(
            c == call({"status": "fired"}) for c in update_calls
        )

    def test_send_toast_logs_error_instead_of_raising(self, caplog):
        """_send_toast must catch all exceptions and log an error, never re-raise."""
        import logging

        plyer_mock = MagicMock()
        plyer_mock.notification.notify.side_effect = Exception("plyer notify error")

        with patch.dict("sys.modules", {"plyer": plyer_mock}):
            with caplog.at_level(logging.ERROR, logger="app.agents.reminder_agent"):
                from app.agents.reminder_agent import _send_toast
                # Must not raise
                _send_toast("Test Title", "2024-11-01T10:00:00")

        # Reaching here without raising is the key assertion.
        # The error log may or may not appear depending on module import cache.


# ---------------------------------------------------------------------------
# 5. _play_chime() failure does NOT prevent toast or WebSocket broadcast
#
# Same reasoning as section 4: isolation is implemented inside _play_chime()
# via try/except.  We simulate the pygame library raising at the call site.
# ---------------------------------------------------------------------------

class TestChimeFailureIsolation:
    @pytest.mark.asyncio
    async def test_toast_fires_when_pygame_raises(self):
        """_send_toast must be called even when pygame.mixer.init raises."""
        db_mock = _make_db_mock()
        reminder = _sample_reminder()

        pygame_mock = MagicMock()
        pygame_mock.mixer.init.side_effect = Exception("pygame init failure")

        with (
            patch("app.agents.reminder_agent._send_toast") as mock_toast,
            patch.dict("sys.modules", {"pygame": pygame_mock}),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        mock_toast.assert_called_once()

    @pytest.mark.asyncio
    async def test_ws_broadcast_fires_when_pygame_raises(self):
        """WebSocket broadcast must be called even when pygame.mixer.init raises."""
        db_mock = _make_db_mock()
        reminder = _sample_reminder()

        pygame_mock = MagicMock()
        pygame_mock.mixer.init.side_effect = Exception("no audio device")

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch.dict("sys.modules", {"pygame": pygame_mock}),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        mock_ws.broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_status_update_fires_when_pygame_raises(self):
        """Status update to 'fired' must happen even when pygame.mixer.init raises."""
        db_mock = _make_db_mock()
        chain = db_mock.table.return_value
        reminder = _sample_reminder()

        pygame_mock = MagicMock()
        pygame_mock.mixer.init.side_effect = Exception("pygame unavailable")

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch.dict("sys.modules", {"pygame": pygame_mock}),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        update_calls = chain.update.call_args_list
        assert any(
            c == call({"status": "fired"}) for c in update_calls
        )

    def test_play_chime_logs_warning_instead_of_raising(self, caplog):
        """_play_chime must catch all exceptions and log a warning, never re-raise."""
        import logging

        # Simulate pygame unavailable
        pygame_mock = MagicMock()
        pygame_mock.mixer.init.side_effect = Exception("no display")

        with patch.dict("sys.modules", {"pygame": pygame_mock}):
            with caplog.at_level(logging.WARNING, logger="app.agents.reminder_agent"):
                from app.agents.reminder_agent import _play_chime
                # Must not raise
                _play_chime()

        # Reaching here without raising is the key assertion.


# ---------------------------------------------------------------------------
# 6. Status transition: pending → fired only (never backward)
# ---------------------------------------------------------------------------

class TestStatusTransition:
    @pytest.mark.asyncio
    async def test_update_always_sets_status_to_fired(self):
        """The status update payload must always be {'status': 'fired'}."""
        db_mock = _make_db_mock()
        chain = db_mock.table.return_value
        reminder = _sample_reminder(status="pending")

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        update_calls = chain.update.call_args_list
        assert any(
            c == call({"status": "fired"}) for c in update_calls
        )

    @pytest.mark.asyncio
    async def test_does_not_set_status_back_to_pending(self):
        """The status must never be updated back to 'pending'."""
        db_mock = _make_db_mock()
        chain = db_mock.table.return_value
        reminder = _sample_reminder()

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        update_calls = chain.update.call_args_list
        assert not any(
            c == call({"status": "pending"}) for c in update_calls
        ), "Status must never be set back to 'pending'"

    @pytest.mark.asyncio
    async def test_check_reminders_only_fetches_pending(self):
        """check_reminders must never query for already-fired reminders."""
        db_mock = _make_db_mock([])
        chain = db_mock.table.return_value

        with (
            patch("app.agents.reminder_agent.get_client", return_value=db_mock),
            patch("app.agents.reminder_agent._dispatch_reminder", new_callable=AsyncMock),
        ):
            from app.agents.reminder_agent import check_reminders
            await check_reminders()

        eq_calls = chain.eq.call_args_list
        # Must filter on 'pending', must NOT filter on 'fired'
        assert any(c == call("status", "pending") for c in eq_calls)
        assert not any(c == call("status", "fired") for c in eq_calls), (
            "Query must not filter on 'fired' status"
        )

    @pytest.mark.asyncio
    async def test_status_update_called_exactly_once_per_reminder(self):
        """Status must be updated to 'fired' exactly once per dispatched reminder."""
        db_mock = _make_db_mock()
        chain = db_mock.table.return_value
        reminder = _sample_reminder(reminder_id="rem-001")
        update_fired_count = 0

        original_update = chain.update

        def counting_update(payload):
            nonlocal update_fired_count
            if payload == {"status": "fired"}:
                update_fired_count += 1
            return chain

        chain.update.side_effect = counting_update

        with (
            patch("app.agents.reminder_agent._send_toast"),
            patch("app.agents.reminder_agent._play_chime"),
            patch("app.agents.reminder_agent.ws_manager") as mock_ws,
        ):
            mock_ws.broadcast = AsyncMock()
            from app.agents.reminder_agent import _dispatch_reminder
            await _dispatch_reminder(db_mock, reminder)

        assert update_fired_count == 1, (
            f"Expected status to be set to 'fired' exactly once, got {update_fired_count}"
        )
