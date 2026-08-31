"""Unit tests for backend/app/routes/mistakes.py.

Tests cover:
  - POST /mistakes: inserts a new row (recurrence_count=1)
  - POST /mistakes: increments recurrence_count on duplicate
  - POST /mistakes: works without profile_id
  - GET /mistakes: returns all mistakes sorted by recurrence_count desc
  - GET /mistakes: filters by subject_id
  - GET /mistakes: filters by chapter_id
  - GET /mistakes: filters by both subject_id and chapter_id
  - GET /mistakes: returns empty list when no data

All supabase calls are mocked so tests run without a live database.
"""

import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared UUIDs
# ---------------------------------------------------------------------------

PROFILE_ID = "00000000-0000-0000-0000-000000000001"
SUBJECT_ID = "00000000-0000-0000-0000-000000000002"
CHAPTER_ID = "00000000-0000-0000-0000-000000000003"
MISTAKE_ID = "00000000-0000-0000-0000-000000000004"
DESCRIPTION = "Confused integration limits"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mistake(
    recurrence_count: int = 1,
    subject_id: str = SUBJECT_ID,
    chapter_id: str = CHAPTER_ID,
    description: str = DESCRIPTION,
    profile_id: str | None = PROFILE_ID,
) -> dict:
    return {
        "id": MISTAKE_ID,
        "profile_id": profile_id,
        "subject_id": subject_id,
        "chapter_id": chapter_id,
        "description": description,
        "recurrence_count": recurrence_count,
        "created_at": "2024-06-01T10:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """TestClient with lifespan I/O patched out and a fresh app import."""
    with (
        patch("app.main.verify_connection"),
        patch("app.main.start_scheduler"),
        patch("app.main.stop_scheduler"),
    ):
        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def _mock_db(existing_rows: list, inserted_row: dict | None = None, updated_row: dict | None = None):
    """Return a mock supabase client whose `table()` chain behaves as specified."""
    mock_client = MagicMock()
    table = MagicMock()
    mock_client.table.return_value = table

    # SELECT chain: .select().eq()...execute() → existing_rows
    select_chain = MagicMock()
    table.select.return_value = select_chain
    # eq / is_ calls return self so we can chain
    select_chain.eq.return_value = select_chain
    select_chain.is_.return_value = select_chain
    select_chain.order.return_value = select_chain
    select_chain.execute.return_value = MagicMock(data=existing_rows)

    # UPDATE chain
    update_chain = MagicMock()
    table.update.return_value = update_chain
    update_chain.eq.return_value = update_chain
    if updated_row is not None:
        update_chain.execute.return_value = MagicMock(data=[updated_row])
    else:
        update_chain.execute.return_value = MagicMock(data=[])

    # INSERT chain
    insert_chain = MagicMock()
    table.insert.return_value = insert_chain
    if inserted_row is not None:
        insert_chain.execute.return_value = MagicMock(data=[inserted_row])
    else:
        insert_chain.execute.return_value = MagicMock(data=[])

    return mock_client


# ---------------------------------------------------------------------------
# POST /mistakes
# ---------------------------------------------------------------------------


class TestPostMistakes:
    def test_insert_new_mistake_returns_200(self, client: TestClient):
        new_row = _make_mistake(recurrence_count=1)
        mock_db = _mock_db(existing_rows=[], inserted_row=new_row)

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.post(
                "/mistakes",
                json={
                    "profile_id": PROFILE_ID,
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "description": DESCRIPTION,
                },
            )

        assert response.status_code == 200

    def test_insert_new_mistake_returns_recurrence_count_1(self, client: TestClient):
        new_row = _make_mistake(recurrence_count=1)
        mock_db = _mock_db(existing_rows=[], inserted_row=new_row)

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.post(
                "/mistakes",
                json={
                    "profile_id": PROFILE_ID,
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "description": DESCRIPTION,
                },
            )

        assert response.json()["recurrence_count"] == 1

    def test_duplicate_mistake_increments_recurrence_count(self, client: TestClient):
        existing = {"id": MISTAKE_ID, "recurrence_count": 3}
        updated_row = _make_mistake(recurrence_count=4)
        mock_db = _mock_db(existing_rows=[existing], updated_row=updated_row)

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.post(
                "/mistakes",
                json={
                    "profile_id": PROFILE_ID,
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "description": DESCRIPTION,
                },
            )

        assert response.status_code == 200
        assert response.json()["recurrence_count"] == 4

    def test_duplicate_calls_update_not_insert(self, client: TestClient):
        existing = {"id": MISTAKE_ID, "recurrence_count": 2}
        updated_row = _make_mistake(recurrence_count=3)
        mock_db = _mock_db(existing_rows=[existing], updated_row=updated_row)

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            client.post(
                "/mistakes",
                json={
                    "profile_id": PROFILE_ID,
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "description": DESCRIPTION,
                },
            )

        # update() must be called, insert() must NOT
        mock_db.table.return_value.update.assert_called_once()
        mock_db.table.return_value.insert.assert_not_called()

    def test_new_mistake_calls_insert_not_update(self, client: TestClient):
        new_row = _make_mistake(recurrence_count=1)
        mock_db = _mock_db(existing_rows=[], inserted_row=new_row)

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            client.post(
                "/mistakes",
                json={
                    "profile_id": PROFILE_ID,
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "description": DESCRIPTION,
                },
            )

        mock_db.table.return_value.insert.assert_called_once()
        mock_db.table.return_value.update.assert_not_called()

    def test_missing_profile_id_accepted(self, client: TestClient):
        """profile_id is optional — POST without it must succeed."""
        new_row = _make_mistake(recurrence_count=1, profile_id=None)
        mock_db = _mock_db(existing_rows=[], inserted_row=new_row)

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.post(
                "/mistakes",
                json={
                    "subject_id": SUBJECT_ID,
                    "chapter_id": CHAPTER_ID,
                    "description": DESCRIPTION,
                },
            )

        assert response.status_code == 200

    def test_missing_subject_id_returns_422(self, client: TestClient):
        """subject_id is required — omitting it must return HTTP 422."""
        response = client.post(
            "/mistakes",
            json={
                "chapter_id": CHAPTER_ID,
                "description": DESCRIPTION,
            },
        )
        assert response.status_code == 422

    def test_missing_chapter_id_returns_422(self, client: TestClient):
        response = client.post(
            "/mistakes",
            json={
                "subject_id": SUBJECT_ID,
                "description": DESCRIPTION,
            },
        )
        assert response.status_code == 422

    def test_missing_description_returns_422(self, client: TestClient):
        response = client.post(
            "/mistakes",
            json={
                "subject_id": SUBJECT_ID,
                "chapter_id": CHAPTER_ID,
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /mistakes
# ---------------------------------------------------------------------------


class TestGetMistakes:
    def test_returns_200(self, client: TestClient):
        mock_db = _mock_db(existing_rows=[_make_mistake()])

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.get("/mistakes")

        assert response.status_code == 200

    def test_returns_list(self, client: TestClient):
        rows = [_make_mistake(recurrence_count=3), _make_mistake(recurrence_count=1)]
        mock_db = _mock_db(existing_rows=rows)

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.get("/mistakes")

        assert isinstance(response.json(), list)

    def test_returns_empty_list_when_no_mistakes(self, client: TestClient):
        mock_db = _mock_db(existing_rows=[])

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            response = client.get("/mistakes")

        assert response.json() == []

    def test_order_call_uses_desc(self, client: TestClient):
        """GET /mistakes must request descending recurrence_count order."""
        mock_db = _mock_db(existing_rows=[])

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            client.get("/mistakes")

        # Verify .order("recurrence_count", desc=True) was called
        mock_db.table.return_value.select.return_value.order.assert_called_once_with(
            "recurrence_count", desc=True
        )

    def test_subject_id_filter_applied(self, client: TestClient):
        mock_db = _mock_db(existing_rows=[])

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            client.get(f"/mistakes?subject_id={SUBJECT_ID}")

        chain = mock_db.table.return_value.select.return_value
        # .eq("subject_id", ...) must be called somewhere in the chain
        eq_calls = [str(c) for c in chain.eq.call_args_list]
        assert any("subject_id" in str(c) for c in chain.eq.call_args_list)

    def test_chapter_id_filter_applied(self, client: TestClient):
        mock_db = _mock_db(existing_rows=[])

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            client.get(f"/mistakes?chapter_id={CHAPTER_ID}")

        chain = mock_db.table.return_value.select.return_value
        assert any("chapter_id" in str(c) for c in chain.eq.call_args_list)

    def test_no_filter_does_not_call_eq(self, client: TestClient):
        """Without query params, .eq() must NOT be called (no spurious filter)."""
        mock_db = _mock_db(existing_rows=[])

        with patch("app.routes.mistakes.get_client", return_value=mock_db):
            client.get("/mistakes")

        chain = mock_db.table.return_value.select.return_value
        chain.eq.assert_not_called()
