"""Integration tests for the full REST + WebSocket flow.

Exercises the FastAPI app end-to-end using TestClient / httpx.AsyncClient
with mocked Supabase and lifecycle hooks.  All tests use the real router
layer and Pydantic validation — only I/O (DB, scheduler, WS DB fetch) is
stubbed.

Requirements covered: 5.2, 10.2, 11.2, 12.2, 14.3
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared UUIDs / constants
# ---------------------------------------------------------------------------

SUBJECT_ID = "aaaaaaaa-0000-0000-0000-000000000001"
CHAPTER_ID = "bbbbbbbb-0000-0000-0000-000000000002"
PROFILE_ID = "cccccccc-0000-0000-0000-000000000003"
MISTAKE_ID = "dddddddd-0000-0000-0000-000000000004"
REMINDER_ID = "eeeeeeee-0000-0000-0000-000000000005"
TASK_ID = "ffffffff-0000-0000-0000-000000000006"


# ---------------------------------------------------------------------------
# Supabase mock helpers
# ---------------------------------------------------------------------------


def _mock_result(data: list):
    """Minimal Supabase result object."""
    m = MagicMock()
    m.data = data
    return m


def _chainable_mock(return_value):
    """A MagicMock whose *every* attribute also returns a chainable mock
    that ultimately calls .execute() → return_value."""
    result = MagicMock()
    result.execute.return_value = return_value
    # All chaining methods return self so arbitrary .eq().is_().order()... works.
    for method in ("eq", "is_", "neq", "gte", "lte", "order", "limit", "select",
                   "insert", "update", "delete"):
        getattr(result, method).return_value = result
    return result


def _make_supabase_client(
    *,
    select_data: list | None = None,
    insert_data: list | None = None,
    update_data: list | None = None,
):
    """Build a minimal Supabase mock.

    The table() call returns a chain that handles all combination of
    .select / .insert / .update / .eq / .order / .limit / .execute.
    """
    client = MagicMock()

    select_result = _mock_result(select_data if select_data is not None else [])
    insert_result = _mock_result(insert_data if insert_data is not None else [])
    update_result = _mock_result(update_data if update_data is not None else [])

    table_mock = MagicMock()
    client.table.return_value = table_mock

    # Each operation returns a fully chainable mock ending in execute().
    select_chain = _chainable_mock(select_result)
    insert_chain = _chainable_mock(insert_result)
    update_chain = _chainable_mock(update_result)

    table_mock.select.return_value = select_chain
    table_mock.insert.return_value = insert_chain
    table_mock.update.return_value = update_chain

    return client


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """TestClient with lifespan hooks stubbed to no-ops."""
    with (
        patch("app.main.verify_connection", new_callable=AsyncMock),
        patch("app.main.start_scheduler", new_callable=AsyncMock),
        patch("app.main.stop_scheduler", new_callable=AsyncMock),
    ):
        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ===========================================================================
# 1. Task creation stores priority_score
# ===========================================================================


class TestTaskCreationPriorityScore:
    def test_create_task_response_includes_priority_score(self, client: TestClient):
        """POST a study task; the response must include a priority_score field.

        We bypass the REST route (which doesn't expose task creation) and
        directly exercise create_task() through the service layer with a
        mocked DB, then verify the returned dict has priority_score.

        This mirrors how the planner agent calls create_task internally.
        Satisfies Requirement 5.2.
        """
        task_row = {
            "id": TASK_ID,
            "subject_id": SUBJECT_ID,
            "chapter_id": CHAPTER_ID,
            "scheduled_date": "2025-11-01",
            "estimated_duration_min": 60,
            "priority_score": 0.5,
            "status": "pending",
        }
        mock_db = _make_supabase_client(insert_data=[task_row])

        with patch("app.services.task_service.get_client", return_value=mock_db):
            from app.services.task_service import create_task
            result = create_task(
                {
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "scheduled_date": "2025-11-01",
                    "estimated_duration_min": 60,
                    "weakness_score": 0.8,
                    "board_weightage": 0.6,
                }
            )

        assert "priority_score" in result
        assert isinstance(result["priority_score"], float)

    def test_create_task_priority_score_in_insert_payload(self, client: TestClient):
        """The insert call must include priority_score in the data sent to DB."""
        task_row = {"id": TASK_ID, "priority_score": 0.5}
        mock_db = MagicMock()
        insert_chain = MagicMock()
        insert_chain.execute.return_value = _mock_result([task_row])
        table_mock = MagicMock()
        table_mock.insert.return_value = insert_chain
        mock_db.table.return_value = table_mock

        with patch("app.services.task_service.get_client", return_value=mock_db):
            from app.services.task_service import create_task
            create_task(
                {
                    "subject_id": SUBJECT_ID,
                    "weakness_score": 0.7,
                    "board_weightage": 0.5,
                    "estimated_duration_min": 45,
                }
            )

        # Extract the dict passed to insert()
        call_args = table_mock.insert.call_args
        inserted_payload = call_args[0][0]
        assert "priority_score" in inserted_payload


# ===========================================================================
# 2 & 3. Sleep log validation
# ===========================================================================


class TestSleepLogValidation:
    def test_sleep_end_equal_to_start_returns_201_overnight(self, client: TestClient):
        """sleep_end == sleep_start is treated as 24 h (valid) — returns 201.

        The overnight logic adds a day, so same time = 24 h sleep.
        Satisfies Requirement 10.2 (valid interval accepted).
        """
        sleep_row = {
            "id": "sl-001",
            "sleep_start": "06:00",
            "sleep_end": "06:00",
            "total_sleep_hours": 24.0,
            "log_date": "2025-01-01",
        }
        mock_db = _make_supabase_client(insert_data=[sleep_row])

        with patch("app.routes.sleep_logs.get_client", return_value=mock_db):
            response = client.post(
                "/sleep-logs",
                json={
                    "sleep_start": "06:00",
                    "sleep_end": "06:00",
                    "log_date": "2025-01-01",
                },
            )

        assert response.status_code == 201

    def test_overnight_sleep_earlier_end_accepted(self, client: TestClient):
        """sleep_start=10:00, sleep_end=08:00 → overnight 22 h sleep → HTTP 201.

        Satisfies Requirement 10.2 (overnight crossing handled correctly).
        """
        sleep_row = {
            "id": "sl-002",
            "sleep_start": "10:00",
            "sleep_end": "08:00",
            "total_sleep_hours": 22.0,
            "log_date": "2025-01-02",
        }
        mock_db = _make_supabase_client(insert_data=[sleep_row])

        with patch("app.routes.sleep_logs.get_client", return_value=mock_db):
            response = client.post(
                "/sleep-logs",
                json={
                    "sleep_start": "10:00",
                    "sleep_end": "08:00",
                    "log_date": "2025-01-02",
                },
            )

        assert response.status_code == 201

    def test_sleep_log_stores_total_sleep_hours(self, client: TestClient):
        """total_sleep_hours in the DB insert payload must equal the interval.

        sleep_start=22:00, sleep_end=06:00 → 8 hours.
        """
        sleep_row = {
            "id": "sl-003",
            "sleep_start": "22:00",
            "sleep_end": "06:00",
            "total_sleep_hours": 8.0,
        }
        inserted_payloads: list[dict] = []

        mock_db = MagicMock()
        table_mock = MagicMock()
        insert_chain = MagicMock()
        insert_chain.execute.return_value = _mock_result([sleep_row])

        def capture_insert(data):
            inserted_payloads.append(data)
            return insert_chain

        table_mock.insert.side_effect = capture_insert
        mock_db.table.return_value = table_mock

        with patch("app.routes.sleep_logs.get_client", return_value=mock_db):
            response = client.post(
                "/sleep-logs",
                json={"sleep_start": "22:00", "sleep_end": "06:00"},
            )

        assert response.status_code == 201
        assert len(inserted_payloads) == 1
        assert inserted_payloads[0]["total_sleep_hours"] == pytest.approx(8.0)


# ===========================================================================
# 4. Mistake recurrence increments on duplicate
# ===========================================================================


class TestMistakeRecurrence:
    def test_duplicate_mistake_calls_update_not_insert(self, client: TestClient):
        """When an existing row matches, POST /mistakes must UPDATE (not INSERT).

        Satisfies Requirement 11.2.
        """
        existing = {"id": MISTAKE_ID, "recurrence_count": 2}
        updated_row = {
            "id": MISTAKE_ID,
            "subject_id": SUBJECT_ID,
            "chapter_id": CHAPTER_ID,
            "description": "Wrong sign convention",
            "recurrence_count": 3,
        }

        mock_db = MagicMock()
        table_mock = MagicMock()
        mock_db.table.return_value = table_mock

        # SELECT returns the existing row
        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.is_.return_value = select_chain
        select_chain.execute.return_value = _mock_result([existing])
        table_mock.select.return_value = select_chain

        # UPDATE chain
        update_chain = MagicMock()
        update_chain.eq.return_value = update_chain
        update_chain.execute.return_value = _mock_result([updated_row])
        table_mock.update.return_value = update_chain

        # INSERT chain (should NOT be called)
        insert_chain = MagicMock()
        insert_chain.execute.return_value = _mock_result([])
        table_mock.insert.return_value = insert_chain

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.post(
                "/mistakes",
                json={
                    "profile_id": PROFILE_ID,
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "description": "Wrong sign convention",
                },
            )

        assert response.status_code == 200
        table_mock.update.assert_called_once()
        table_mock.insert.assert_not_called()
        assert response.json()["recurrence_count"] == 3

    def test_new_mistake_inserts_with_recurrence_count_one(self, client: TestClient):
        """A brand-new mistake must be inserted with recurrence_count=1."""
        new_row = {
            "id": MISTAKE_ID,
            "subject_id": SUBJECT_ID,
            "chapter_id": CHAPTER_ID,
            "description": "Forgot sign",
            "recurrence_count": 1,
        }

        mock_db = MagicMock()
        table_mock = MagicMock()
        mock_db.table.return_value = table_mock

        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.is_.return_value = select_chain
        select_chain.execute.return_value = _mock_result([])
        table_mock.select.return_value = select_chain

        insert_chain = MagicMock()
        insert_chain.execute.return_value = _mock_result([new_row])
        table_mock.insert.return_value = insert_chain

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.post(
                "/mistakes",
                json={
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "description": "Forgot sign",
                },
            )

        assert response.status_code == 200
        assert response.json()["recurrence_count"] == 1
        table_mock.insert.assert_called_once()
        table_mock.update.assert_not_called()


# ===========================================================================
# 5 & 6. Test score validation
# ===========================================================================


class TestScoreValidation:
    def test_negative_score_returns_400(self, client: TestClient):
        """POST /tests with score=-1 must return HTTP 400.

        Satisfies Requirement 12.2.
        """
        response = client.post(
            "/tests/",
            json={
                "subject_id": SUBJECT_ID,
                "score": -1,
                "max_score": 100,
            },
        )
        assert response.status_code == 400

    def test_score_exceeding_max_returns_400(self, client: TestClient):
        """POST /tests with score=110, max_score=100 must return HTTP 400.

        Satisfies Requirement 12.2.
        """
        response = client.post(
            "/tests/",
            json={
                "subject_id": SUBJECT_ID,
                "score": 110,
                "max_score": 100,
            },
        )
        assert response.status_code == 400

    def test_valid_score_is_accepted(self, client: TestClient):
        """A valid score within range must return HTTP 201."""
        test_row = {
            "id": "test-001",
            "subject_id": SUBJECT_ID,
            "score": 85.0,
            "max_score": 100.0,
            "percentage": 85.0,
        }
        mock_db = _make_supabase_client(insert_data=[test_row])

        with patch("app.routes.tests.get_client", return_value=mock_db):
            response = client.post(
                "/tests/",
                json={
                    "subject_id": SUBJECT_ID,
                    "score": 85,
                    "max_score": 100,
                },
            )

        assert response.status_code == 201

    def test_zero_score_is_valid(self, client: TestClient):
        """score=0 must be valid (boundary case)."""
        test_row = {
            "id": "test-002",
            "subject_id": SUBJECT_ID,
            "score": 0.0,
            "max_score": 50.0,
            "percentage": 0.0,
        }
        mock_db = _make_supabase_client(insert_data=[test_row])

        with patch("app.routes.tests.get_client", return_value=mock_db):
            response = client.post(
                "/tests/",
                json={
                    "subject_id": SUBJECT_ID,
                    "score": 0,
                    "max_score": 50,
                },
            )

        assert response.status_code == 201

    def test_score_equal_to_max_is_valid(self, client: TestClient):
        """score==max_score must be valid (perfect score boundary)."""
        test_row = {
            "id": "test-003",
            "subject_id": SUBJECT_ID,
            "score": 100.0,
            "max_score": 100.0,
            "percentage": 100.0,
        }
        mock_db = _make_supabase_client(insert_data=[test_row])

        with patch("app.routes.tests.get_client", return_value=mock_db):
            response = client.post(
                "/tests/",
                json={
                    "subject_id": SUBJECT_ID,
                    "score": 100,
                    "max_score": 100,
                },
            )

        assert response.status_code == 201


# ===========================================================================
# 7. Reminder created with pending status
# ===========================================================================


class TestReminderCreation:
    def test_reminder_created_with_pending_status(self, client: TestClient):
        """POST /reminders must insert a row with status='pending'.

        Satisfies Requirement 14.2.
        """
        reminder_row = {
            "id": REMINDER_ID,
            "title": "Start Physics revision",
            "scheduled_at": "2025-11-01T09:30:00",
            "status": "pending",
        }

        inserted_payloads: list[dict] = []

        mock_db = MagicMock()
        table_mock = MagicMock()
        insert_chain = MagicMock()
        insert_chain.execute.return_value = _mock_result([reminder_row])

        def capture_insert(data):
            inserted_payloads.append(data)
            return insert_chain

        table_mock.insert.side_effect = capture_insert
        mock_db.table.return_value = table_mock

        with patch("app.routes.reminders.get_client", return_value=mock_db):
            response = client.post(
                "/reminders",
                json={
                    "title": "Start Physics revision",
                    "scheduled_at": "2025-11-01T09:30:00",
                },
            )

        assert response.status_code == 201
        assert len(inserted_payloads) == 1
        assert inserted_payloads[0]["status"] == "pending"

    def test_reminder_response_contains_id(self, client: TestClient):
        """The created reminder response must contain the row id."""
        reminder_row = {
            "id": REMINDER_ID,
            "title": "Chemistry quiz",
            "scheduled_at": "2025-11-02T14:00:00",
            "status": "pending",
        }
        mock_db = _make_supabase_client(insert_data=[reminder_row])

        with patch("app.routes.reminders.get_client", return_value=mock_db):
            response = client.post(
                "/reminders",
                json={
                    "title": "Chemistry quiz",
                    "scheduled_at": "2025-11-02T14:00:00",
                },
            )

        assert response.status_code == 201
        assert response.json()["id"] == REMINDER_ID


# ===========================================================================
# 8. GET /reminders returns a list
# ===========================================================================


class TestGetReminders:
    def test_get_reminders_returns_list(self, client: TestClient):
        """GET /reminders must return a JSON array.

        Satisfies Requirement 14.5.
        """
        reminders = [
            {
                "id": REMINDER_ID,
                "title": "Morning review",
                "scheduled_at": "2025-11-01T08:00:00",
                "status": "pending",
            }
        ]
        mock_db = _make_supabase_client(select_data=reminders)

        with patch("app.routes.reminders.get_client", return_value=mock_db):
            response = client.get("/reminders")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_reminders_empty_list(self, client: TestClient):
        """GET /reminders with no matching rows must return an empty list."""
        mock_db = _make_supabase_client(select_data=[])

        with patch("app.routes.reminders.get_client", return_value=mock_db):
            response = client.get("/reminders")

        assert response.status_code == 200
        assert response.json() == []


# ===========================================================================
# 9. GET /health returns 200
# ===========================================================================


class TestHealth:
    def test_health_returns_200(self, client: TestClient):
        """Basic smoke test — /health must always return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_body(self, client: TestClient):
        """The /health body must be {"status": "ok"}."""
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


# ===========================================================================
# 10. WebSocket sends init event on connect
# ===========================================================================


class TestWebSocketInitEvent:
    def test_websocket_sends_init_event_on_connect(self, client: TestClient):
        """Connecting to /ws must trigger an 'init' event as the first message.

        We mock _get_today_tasks on the ws_manager singleton so that the
        init payload contains a predictable task list.

        Satisfies Requirement 7.2.
        """
        from app.websocket_manager import ws_manager

        sample_tasks = [
            {
                "id": TASK_ID,
                "subject_id": SUBJECT_ID,
                "chapter_id": CHAPTER_ID,
                "priority_score": 0.85,
                "status": "pending",
            }
        ]

        async def mock_get_tasks():
            return sample_tasks

        with patch.object(ws_manager, "_get_today_tasks", side_effect=mock_get_tasks):
            with client.websocket_connect("/ws") as ws:
                raw = ws.receive_text()
                data = json.loads(raw)

        assert data["type"] == "init"
        assert isinstance(data["tasks"], list)

    def test_websocket_init_event_contains_tasks_key(self, client: TestClient):
        """The init event payload must have a 'tasks' key."""
        from app.websocket_manager import ws_manager

        async def mock_get_tasks():
            return []

        with patch.object(ws_manager, "_get_today_tasks", side_effect=mock_get_tasks):
            with client.websocket_connect("/ws") as ws:
                raw = ws.receive_text()
                data = json.loads(raw)

        assert "tasks" in data
        assert data["type"] == "init"
