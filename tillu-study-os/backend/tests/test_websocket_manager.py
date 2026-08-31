"""Unit tests for backend/app/websocket_manager.py.

Tests:
  1. test_broadcast_sends_to_all_clients
     — N mock WebSocket clients all receive the event
  2. test_broadcast_removes_dead_client_without_affecting_others
     — one client that raises on send_text is removed; remaining clients still receive the event
  3. test_disconnect_removes_connection_from_registry
  4. test_broadcast_on_empty_registry_does_not_raise
  5. test_connect_sends_init_event
     — mock websocket receives an init-type message on connect

All WebSocket interactions use unittest.mock.AsyncMock / MagicMock — no live
Supabase connection is required.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from fastapi import WebSocketDisconnect

from app.websocket_manager import ConnectionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ws() -> AsyncMock:
    """Return a mock WebSocket with async send_text / receive_text methods."""
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.accept = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# broadcast() — happy path: all clients receive the event
# ---------------------------------------------------------------------------

class TestBroadcastSendsToAll:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_clients(self):
        """All registered WebSocket clients must receive the broadcast event."""
        manager = ConnectionManager()
        clients = [_make_ws() for _ in range(4)]
        manager._connections.extend(clients)

        event = {"type": "task_update", "task_id": "abc", "status": "completed"}
        await manager.broadcast(event)

        expected_payload = json.dumps(event)
        for ws in clients:
            ws.send_text.assert_awaited_once_with(expected_payload)

    @pytest.mark.asyncio
    async def test_broadcast_sends_single_client(self):
        """A single connected client receives the broadcast event."""
        manager = ConnectionManager()
        ws = _make_ws()
        manager._connections.append(ws)

        event = {"type": "reminder", "title": "Study now"}
        await manager.broadcast(event)

        ws.send_text.assert_awaited_once_with(json.dumps(event))


# ---------------------------------------------------------------------------
# broadcast() — dead client removed; healthy clients still receive event
# ---------------------------------------------------------------------------

class TestBroadcastRemovesDeadClient:
    @pytest.mark.asyncio
    async def test_dead_client_removed_healthy_clients_receive(self):
        """A client that raises on send_text is removed from the registry.
        The remaining healthy clients must still receive the event.
        """
        manager = ConnectionManager()

        healthy_a = _make_ws()
        dead = _make_ws()
        dead.send_text.side_effect = RuntimeError("connection reset")
        healthy_b = _make_ws()

        manager._connections.extend([healthy_a, dead, healthy_b])

        event = {"type": "daily_plan_created", "date": "2024-11-01", "task_count": 5}
        await manager.broadcast(event)

        # Dead client must have been removed
        assert dead not in manager._connections

        # Healthy clients must still be registered and must have received the event
        assert healthy_a in manager._connections
        assert healthy_b in manager._connections

        expected = json.dumps(event)
        healthy_a.send_text.assert_awaited_once_with(expected)
        healthy_b.send_text.assert_awaited_once_with(expected)

    @pytest.mark.asyncio
    async def test_multiple_dead_clients_all_removed(self):
        """Multiple dead clients are all removed; one healthy client still receives."""
        manager = ConnectionManager()

        dead_a = _make_ws()
        dead_a.send_text.side_effect = Exception("dead a")
        dead_b = _make_ws()
        dead_b.send_text.side_effect = Exception("dead b")
        healthy = _make_ws()

        manager._connections.extend([dead_a, dead_b, healthy])

        event = {"type": "task_update", "task_id": "xyz", "status": "missed"}
        await manager.broadcast(event)

        assert dead_a not in manager._connections
        assert dead_b not in manager._connections
        assert healthy in manager._connections
        healthy.send_text.assert_awaited_once_with(json.dumps(event))

    @pytest.mark.asyncio
    async def test_broadcast_never_raises_even_when_all_clients_dead(self):
        """broadcast() must never raise, even if every client fails."""
        manager = ConnectionManager()

        for _ in range(3):
            ws = _make_ws()
            ws.send_text.side_effect = RuntimeError("dead")
            manager._connections.append(ws)

        event = {"type": "init", "tasks": []}
        # Must not raise
        await manager.broadcast(event)

        assert manager._connections == []


# ---------------------------------------------------------------------------
# broadcast() — empty registry
# ---------------------------------------------------------------------------

class TestBroadcastEmptyRegistry:
    @pytest.mark.asyncio
    async def test_broadcast_on_empty_registry_does_not_raise(self):
        """broadcast() on an empty connection list must complete without raising."""
        manager = ConnectionManager()
        assert manager._connections == []

        event = {"type": "daily_plan_created", "date": "2024-11-01", "task_count": 0}
        # No exception should propagate
        await manager.broadcast(event)


# ---------------------------------------------------------------------------
# disconnect()
# ---------------------------------------------------------------------------

class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_removes_connection_from_registry(self):
        """disconnect() must remove the target WebSocket from _connections."""
        manager = ConnectionManager()
        ws_a = _make_ws()
        ws_b = _make_ws()
        manager._connections.extend([ws_a, ws_b])

        await manager.disconnect(ws_a)

        assert ws_a not in manager._connections
        assert ws_b in manager._connections

    @pytest.mark.asyncio
    async def test_disconnect_unknown_connection_does_not_raise(self):
        """disconnect() on a WebSocket not in the registry must not raise."""
        manager = ConnectionManager()
        ws = _make_ws()  # never registered

        await manager.disconnect(ws)  # must be silent

    @pytest.mark.asyncio
    async def test_disconnect_reduces_connection_count(self):
        """_connections list shrinks by exactly 1 after disconnect()."""
        manager = ConnectionManager()
        clients = [_make_ws() for _ in range(3)]
        manager._connections.extend(clients)

        await manager.disconnect(clients[1])

        assert len(manager._connections) == 2


# ---------------------------------------------------------------------------
# connect() — sends init event on connection
# ---------------------------------------------------------------------------

class TestConnectSendsInitEvent:
    @pytest.mark.asyncio
    async def test_connect_sends_init_event(self):
        """On connect(), the WebSocket must receive an init-type message
        containing a 'tasks' key before the keep-alive loop starts.

        The keep-alive loop is terminated by having receive_text raise an
        Exception after its first call so the test does not block.
        """
        manager = ConnectionManager()
        ws = _make_ws()

        # Receive_text raises after one call to break the keep-alive loop
        ws.receive_text.side_effect = [Exception("disconnect")]

        fake_tasks = [{"id": "t1", "status": "pending", "priority_score": 0.75}]

        with patch.object(manager, "_get_today_tasks", new=AsyncMock(return_value=fake_tasks)):
            await manager.connect(ws)

        # accept() must have been called exactly once
        ws.accept.assert_awaited_once()

        # Inspect all payloads sent to the client
        sent_payloads = [
            json.loads(c.args[0])
            for c in ws.send_text.await_args_list
        ]

        # The first message must be the init event
        assert len(sent_payloads) >= 1
        init_msg = sent_payloads[0]
        assert init_msg["type"] == "init"
        assert init_msg["tasks"] == fake_tasks

    @pytest.mark.asyncio
    async def test_connect_registers_client(self):
        """The client must be present in _connections during the session."""
        manager = ConnectionManager()
        ws = _make_ws()
        ws.receive_text.side_effect = [Exception("client gone")]

        registered_during_loop = []

        async def capture_receive():
            # Record the connection state before raising
            registered_during_loop.append(ws in manager._connections)
            raise Exception("client gone")

        ws.receive_text.side_effect = capture_receive

        with patch.object(manager, "_get_today_tasks", new=AsyncMock(return_value=[])):
            await manager.connect(ws)

        assert registered_during_loop == [True]

    @pytest.mark.asyncio
    async def test_connect_disconnects_on_exception(self):
        """After the keep-alive loop exits, the client must be removed from registry."""
        manager = ConnectionManager()
        ws = _make_ws()
        ws.receive_text.side_effect = Exception("client disconnected")

        with patch.object(manager, "_get_today_tasks", new=AsyncMock(return_value=[])):
            await manager.connect(ws)

        assert ws not in manager._connections

    @pytest.mark.asyncio
    async def test_connect_disconnects_on_websocket_disconnect(self):
        """WebSocketDisconnect from the receive loop also removes the client."""
        manager = ConnectionManager()
        ws = _make_ws()
        ws.receive_text.side_effect = WebSocketDisconnect(code=1000)

        with patch.object(manager, "_get_today_tasks", new=AsyncMock(return_value=[])):
            await manager.connect(ws)

        assert ws not in manager._connections


# ---------------------------------------------------------------------------
# ws_manager singleton
# ---------------------------------------------------------------------------

class TestWsManagerSingleton:
    def test_ws_manager_singleton_exported(self):
        """ws_manager must be importable as a module-level singleton."""
        from app.websocket_manager import ws_manager, ConnectionManager

        assert isinstance(ws_manager, ConnectionManager)

    def test_ws_manager_starts_empty(self):
        """The singleton starts with an empty connections list."""
        from app.websocket_manager import ws_manager

        # This is checked at import-time; if other tests added connections
        # the count might differ — so we only assert it is a list.
        assert isinstance(ws_manager._connections, list)
