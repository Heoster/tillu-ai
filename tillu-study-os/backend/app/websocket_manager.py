"""WebSocket connection manager.

Stub implementation — full implementation with keep-alive loop and today's-tasks
init event will be completed in task 8.1.
"""

import json
import logging
from typing import List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and fan-out broadcasts."""

    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept connection, register it, send init event, run keep-alive loop."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket client connected; total=%d", len(self._connections))

        # Send initial state event
        initial_tasks = await self._get_today_tasks()
        await websocket.send_text(
            json.dumps({"type": "init", "tasks": initial_tasks})
        )

        # Keep-alive receive loop — exits when client disconnects
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await self.disconnect(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a connection from the registry."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WebSocket client disconnected; total=%d", len(self._connections))

    async def broadcast(self, event: dict) -> None:
        """Send a JSON event to every registered connection.

        Dead connections are silently removed; remaining clients still receive
        the event even if one client fails.
        """
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(json.dumps(event))
            except Exception as exc:
                logger.warning("WebSocket send failed (%s) — removing dead connection", exc)
                dead.append(ws)
        for ws in dead:
            if ws in self._connections:
                self._connections.remove(ws)

    async def _get_today_tasks(self) -> list:
        """Fetch today's tasks from Supabase for the init event."""
        try:
            from app.db import get_client
            from datetime import date

            result = (
                get_client()
                .table("study_tasks")
                .select("*")
                .eq("scheduled_date", str(date.today()))
                .order("priority_score", desc=True)
                .execute()
            )
            return result.data
        except Exception as exc:
            logger.warning("Could not fetch today's tasks for WS init: %s", exc)
            return []


# Shared singleton used throughout the application
ws_manager = ConnectionManager()
