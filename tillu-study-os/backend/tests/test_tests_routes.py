"""Unit tests for backend/app/routes/tests.py.

Covers:
- validate_test_score(): accepts valid inputs, rejects invalid ones (Req 12.2)
- POST /tests: validates and inserts a test score record (Req 12.2, 12.3)
- GET /tests/summary: returns per-subject averages sorted asc by avg (Req 12.4)
- GET /tests: returns all records with optional subject_id filter
- Summary sorts weakest subject first (lowest avg_percentage first)
- Summary handles subjects with no percentage data (NULL rows)

All tests use dependency-injection overrides and mock the Supabase client
so no live database is needed.
"""

import pytest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.routes.tests import validate_test_score


# ---------------------------------------------------------------------------
# validate_test_score() — pure unit tests (no HTTP)
# ---------------------------------------------------------------------------

class TestValidateTestScore:
    def test_valid_score_zero(self):
        """score == 0 with max_score > 0 should not raise."""
        validate_test_score(0.0, 100.0)  # no exception

    def test_valid_score_equals_max(self):
        """score == max_score should not raise."""
        validate_test_score(50.0, 50.0)

    def test_valid_mid_range(self):
        validate_test_score(45.0, 50.0)

    def test_negative_score_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_test_score(-1.0, 50.0)
        assert exc_info.value.status_code == 400

    def test_score_exceeds_max_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_test_score(51.0, 50.0)
        assert exc_info.value.status_code == 400

    def test_max_score_zero_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_test_score(0.0, 0.0)
        assert exc_info.value.status_code == 400

    def test_max_score_negative_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_test_score(0.0, -10.0)
        assert exc_info.value.status_code == 400

    def test_error_detail_mentions_score(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_test_score(60.0, 50.0)
        assert "60.0" in exc_info.value.detail

    def test_error_detail_mentions_max_score_zero(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_test_score(0.0, 0.0)
        assert "max_score" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# HTTP endpoint tests — shared client fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """TestClient with Supabase I/O fully mocked out."""
    with (
        patch("app.main.verify_connection"),
        patch("app.main.start_scheduler"),
        patch("app.main.stop_scheduler"),
    ):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def _make_db_mock(insert_data=None, select_data=None):
    """Build a mock Supabase client for injection via get_client patch."""
    mock_db = MagicMock()

    # --- insert chain: .table().insert().execute() ---
    mock_insert_result = MagicMock()
    mock_insert_result.data = insert_data or []
    (
        mock_db.table.return_value
        .insert.return_value
        .execute.return_value
    ) = mock_insert_result

    # --- select chain: .table().select().order().execute()
    #                   .table().select().eq().order().execute() ---
    mock_select_result = MagicMock()
    mock_select_result.data = select_data or []

    # Build a flexible chain that handles .select().eq().order() and
    # .select().order() by returning the mock result at any .execute() call.
    chain = MagicMock()
    chain.execute.return_value = mock_select_result
    chain.eq.return_value = chain
    chain.order.return_value = chain
    mock_db.table.return_value.select.return_value = chain

    return mock_db


# ---------------------------------------------------------------------------
# POST /tests
# ---------------------------------------------------------------------------

class TestPostTests:
    VALID_PAYLOAD = {
        "subject_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "score": 45.0,
        "max_score": 50.0,
    }

    def _inserted_row(self, **overrides):
        row = {
            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "subject_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "chapter_id": None,
            "profile_id": None,
            "score": 45.0,
            "max_score": 50.0,
            "percentage": 90.0,
            "taken_at": "2024-11-01T10:00:00",
        }
        row.update(overrides)
        return row

    def test_valid_payload_returns_201(self, client):
        db = _make_db_mock(insert_data=[self._inserted_row()])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.post("/tests/", json=self.VALID_PAYLOAD)
        assert resp.status_code == 201

    def test_valid_payload_returns_inserted_row(self, client):
        db = _make_db_mock(insert_data=[self._inserted_row()])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.post("/tests/", json=self.VALID_PAYLOAD)
        body = resp.json()
        assert body["score"] == 45.0
        assert body["max_score"] == 50.0
        assert body["percentage"] == 90.0

    def test_negative_score_returns_400(self, client):
        payload = {**self.VALID_PAYLOAD, "score": -1.0}
        resp = client.post("/tests/", json=payload)
        assert resp.status_code == 400

    def test_score_exceeds_max_returns_400(self, client):
        payload = {**self.VALID_PAYLOAD, "score": 51.0}
        resp = client.post("/tests/", json=payload)
        assert resp.status_code == 400

    def test_max_score_zero_returns_400(self, client):
        payload = {**self.VALID_PAYLOAD, "max_score": 0.0, "score": 0.0}
        resp = client.post("/tests/", json=payload)
        assert resp.status_code == 400

    def test_max_score_negative_returns_400(self, client):
        payload = {**self.VALID_PAYLOAD, "max_score": -5.0, "score": 0.0}
        resp = client.post("/tests/", json=payload)
        assert resp.status_code == 400

    def test_score_zero_is_accepted(self, client):
        row = self._inserted_row(score=0.0, percentage=0.0)
        db = _make_db_mock(insert_data=[row])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.post("/tests/", json={**self.VALID_PAYLOAD, "score": 0.0})
        assert resp.status_code == 201

    def test_score_equals_max_is_accepted(self, client):
        row = self._inserted_row(score=50.0, percentage=100.0)
        db = _make_db_mock(insert_data=[row])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.post("/tests/", json={**self.VALID_PAYLOAD, "score": 50.0})
        assert resp.status_code == 201

    def test_optional_fields_included_when_provided(self, client):
        """profile_id and chapter_id should be forwarded to the DB when present."""
        payload = {
            **self.VALID_PAYLOAD,
            "profile_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "chapter_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        }
        row = self._inserted_row(
            profile_id=payload["profile_id"],
            chapter_id=payload["chapter_id"],
        )
        db = _make_db_mock(insert_data=[row])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.post("/tests/", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["profile_id"] == payload["profile_id"]
        assert body["chapter_id"] == payload["chapter_id"]

    def test_percentage_not_in_insert_payload(self, client):
        """The route must NOT send 'percentage' to the DB (it's GENERATED ALWAYS)."""
        db = _make_db_mock(insert_data=[self._inserted_row()])
        with patch("app.routes.tests.get_client", return_value=db):
            client.post("/tests/", json=self.VALID_PAYLOAD)
        # Retrieve what was actually passed to .insert()
        insert_call_args = db.table.return_value.insert.call_args
        inserted_payload = insert_call_args[0][0]
        assert "percentage" not in inserted_payload


# ---------------------------------------------------------------------------
# GET /tests/summary
# ---------------------------------------------------------------------------

SUBJECT_A = "aaaa0000-0000-0000-0000-000000000000"
SUBJECT_B = "bbbb0000-0000-0000-0000-000000000000"


class TestGetTestsSummary:
    def _mock_tests(self, rows):
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = rows
        chain = MagicMock()
        chain.execute.return_value = mock_result
        mock_db.table.return_value.select.return_value = chain
        return mock_db

    def test_returns_200(self, client):
        db = self._mock_tests([])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        assert resp.status_code == 200

    def test_empty_database_returns_empty_list(self, client):
        db = self._mock_tests([])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        assert resp.json() == []

    def test_single_subject_single_record(self, client):
        rows = [{"subject_id": SUBJECT_A, "percentage": 80.0}]
        db = self._mock_tests(rows)
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        body = resp.json()
        assert len(body) == 1
        assert body[0]["subject_id"] == SUBJECT_A
        assert body[0]["avg_percentage"] == pytest.approx(80.0)

    def test_single_subject_multiple_records_averages_correctly(self, client):
        rows = [
            {"subject_id": SUBJECT_A, "percentage": 60.0},
            {"subject_id": SUBJECT_A, "percentage": 80.0},
            {"subject_id": SUBJECT_A, "percentage": 100.0},
        ]
        db = self._mock_tests(rows)
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        body = resp.json()
        assert body[0]["avg_percentage"] == pytest.approx(80.0)

    def test_two_subjects_sorted_weakest_first(self, client):
        rows = [
            {"subject_id": SUBJECT_A, "percentage": 90.0},  # stronger
            {"subject_id": SUBJECT_B, "percentage": 50.0},  # weaker
        ]
        db = self._mock_tests(rows)
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        body = resp.json()
        assert len(body) == 2
        assert body[0]["subject_id"] == SUBJECT_B   # weakest first
        assert body[1]["subject_id"] == SUBJECT_A

    def test_null_percentage_rows_excluded(self, client):
        """Rows where percentage is None (NULL) must not affect the average."""
        rows = [
            {"subject_id": SUBJECT_A, "percentage": 80.0},
            {"subject_id": SUBJECT_A, "percentage": None},  # should be skipped
        ]
        db = self._mock_tests(rows)
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        body = resp.json()
        assert len(body) == 1
        assert body[0]["avg_percentage"] == pytest.approx(80.0)

    def test_subject_with_only_null_percentages_excluded_from_summary(self, client):
        """A subject whose every percentage row is NULL must not appear in summary."""
        rows = [
            {"subject_id": SUBJECT_A, "percentage": None},
            {"subject_id": SUBJECT_A, "percentage": None},
        ]
        db = self._mock_tests(rows)
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        assert resp.json() == []

    def test_avg_percentage_rounded_to_two_decimals(self, client):
        rows = [
            {"subject_id": SUBJECT_A, "percentage": 100.0},
            {"subject_id": SUBJECT_A, "percentage": 0.0},
            {"subject_id": SUBJECT_A, "percentage": 1.0},
        ]
        db = self._mock_tests(rows)
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        avg = resp.json()[0]["avg_percentage"]
        # (100 + 0 + 1) / 3 ≈ 33.67
        assert avg == pytest.approx(33.67, abs=0.01)

    def test_response_has_subject_id_and_avg_percentage_keys(self, client):
        rows = [{"subject_id": SUBJECT_A, "percentage": 75.0}]
        db = self._mock_tests(rows)
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/summary")
        item = resp.json()[0]
        assert "subject_id" in item
        assert "avg_percentage" in item


# ---------------------------------------------------------------------------
# GET /tests
# ---------------------------------------------------------------------------

class TestListTests:
    def _mock_db_for_list(self, rows):
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = rows
        chain = MagicMock()
        chain.execute.return_value = mock_result
        chain.eq.return_value = chain
        chain.order.return_value = chain
        mock_db.table.return_value.select.return_value = chain
        return mock_db

    def test_returns_200(self, client):
        db = self._mock_db_for_list([])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/")
        assert resp.status_code == 200

    def test_empty_database_returns_empty_list(self, client):
        db = self._mock_db_for_list([])
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/")
        assert resp.json() == []

    def test_returns_all_records(self, client):
        rows = [
            {"id": "1", "subject_id": SUBJECT_A, "score": 40.0, "max_score": 50.0, "percentage": 80.0},
            {"id": "2", "subject_id": SUBJECT_B, "score": 30.0, "max_score": 50.0, "percentage": 60.0},
        ]
        db = self._mock_db_for_list(rows)
        with patch("app.routes.tests.get_client", return_value=db):
            resp = client.get("/tests/")
        assert len(resp.json()) == 2

    def test_subject_id_filter_calls_eq(self, client):
        """When ?subject_id= is provided, .eq() must be called on the query."""
        db = self._mock_db_for_list([])
        with patch("app.routes.tests.get_client", return_value=db):
            client.get(f"/tests/?subject_id={SUBJECT_A}")
        chain = db.table.return_value.select.return_value
        chain.eq.assert_called_once_with("subject_id", SUBJECT_A)
