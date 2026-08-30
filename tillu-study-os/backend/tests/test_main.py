"""Unit tests for backend/app/main.py.

Tests:
  - GET /health returns HTTP 200 with {"status": "ok"}
  - An unhandled exception inside a route returns HTTP 500 with a JSON error body
  - Startup sequence: verify_connection and start_scheduler are called during lifespan

All tests patch out I/O-bound startup hooks (DB probe, scheduler) so they
run without a live Supabase instance.
"""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Return the real app with startup I/O patched to no-ops.

    Using TestClient as a context manager triggers the lifespan, so we must
    patch at the module level before the lifespan fires.
    """
    return "app.main"  # import path — used in the fixtures below


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """TestClient with lifespan enabled and all external I/O stubbed out.

    Patches are applied at the 'app.main.*' level because main.py uses
    'from ... import' — patching the source module after the fact would
    have no effect on the already-resolved names inside main.py.
    """
    with (
        patch("app.main.verify_connection", new_callable=AsyncMock),
        patch("app.main.start_scheduler", new_callable=AsyncMock),
        patch("app.main.stop_scheduler", new_callable=AsyncMock),
    ):
        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_body(self, client: TestClient):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    def test_health_content_type_is_json(self, client: TestClient):
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Global exception handler — HTTP 500 on unhandled exceptions
# ---------------------------------------------------------------------------

class TestGlobalExceptionHandler:
    def test_unhandled_exception_returns_500(self, client: TestClient):
        """A route that raises an unhandled exception must yield HTTP 500."""
        # Register a temporary error route on the *running* app and call it.
        # We do this via a dedicated fixture-style approach: add a route that
        # intentionally raises, then hit it.
        from app.main import app

        @app.get("/_test_error")
        async def _error_route():
            raise RuntimeError("deliberate test error")

        response = client.get("/_test_error")
        assert response.status_code == 500

    def test_unhandled_exception_returns_json_body(self, client: TestClient):
        """HTTP 500 response must include a JSON body with an 'error' key."""
        from app.main import app

        @app.get("/_test_error_body")
        async def _error_body_route():
            raise ValueError("json error body test")

        response = client.get("/_test_error_body")
        assert response.status_code == 500
        body = response.json()
        assert "error" in body

    def test_unhandled_exception_error_message_in_body(self, client: TestClient):
        """The 'error' value in the 500 body should contain the exception message."""
        from app.main import app

        @app.get("/_test_error_msg")
        async def _error_msg_route():
            raise RuntimeError("unique-sentinel-message")

        response = client.get("/_test_error_msg")
        assert response.status_code == 500
        assert "unique-sentinel-message" in response.json()["error"]


# ---------------------------------------------------------------------------
# CORS header check
# ---------------------------------------------------------------------------

class TestCORS:
    def test_cors_header_present_for_allowed_origin(self, client: TestClient):
        """Preflight / simple request from the configured frontend origin should
        include Access-Control-Allow-Origin in the response."""
        from app.config import settings

        response = client.get(
            "/health",
            headers={"Origin": settings.frontend_origin},
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == settings.frontend_origin


# ---------------------------------------------------------------------------
# Startup lifecycle
# ---------------------------------------------------------------------------

class TestLifespan:
    """Lifespan tests patch the names as bound inside main.py (i.e. 'app.main.*')
    because main.py imports them with 'from ... import', so patching the source
    module after the fact has no effect on the already-resolved references."""

    def test_verify_connection_called_on_startup(self):
        """verify_connection() must be awaited during lifespan startup."""
        with (
            patch("app.main.verify_connection", new_callable=AsyncMock) as mock_verify,
            patch("app.main.start_scheduler", new_callable=AsyncMock),
            patch("app.main.stop_scheduler", new_callable=AsyncMock),
        ):
            from app.main import app

            with TestClient(app, raise_server_exceptions=False):
                pass  # lifespan runs on enter

            mock_verify.assert_awaited_once()

    def test_start_scheduler_called_on_startup(self):
        """start_scheduler() must be awaited during lifespan startup."""
        with (
            patch("app.main.verify_connection", new_callable=AsyncMock),
            patch("app.main.start_scheduler", new_callable=AsyncMock) as mock_start,
            patch("app.main.stop_scheduler", new_callable=AsyncMock),
        ):
            from app.main import app

            with TestClient(app, raise_server_exceptions=False):
                pass

            mock_start.assert_awaited_once()

    def test_stop_scheduler_called_on_shutdown(self):
        """stop_scheduler() must be awaited during lifespan shutdown."""
        with (
            patch("app.main.verify_connection", new_callable=AsyncMock),
            patch("app.main.start_scheduler", new_callable=AsyncMock),
            patch("app.main.stop_scheduler", new_callable=AsyncMock) as mock_stop,
        ):
            from app.main import app

            with TestClient(app, raise_server_exceptions=False):
                pass  # exits context → triggers shutdown

            mock_stop.assert_awaited_once()
