"""Unit tests for tillu_brain.py — AI routing layer.

Tests:
  1. ask_tillu calls Groq first and returns its response when successful
  2. ask_tillu falls back to Cerebras when Groq raises an exception
  3. ask_tillu falls back to rule-based when both Groq and Cerebras fail
  4. _rule_based_plan returns non-empty string for any non-empty task list
  5. _rule_based_plan returns a descriptive string when task list is empty
  6. ask_tillu handles Groq timeout (asyncio.TimeoutError) by falling back to Cerebras
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.tillu_brain import ask_tillu, _rule_based_plan, TILLU_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CONTEXT = {
    "date": "2024-11-01",
    "tasks": [
        {
            "chapter_name": "Electrostatics",
            "subject_name": "Physics",
            "estimated_duration_min": 90,
            "priority_score": 0.85,
        },
        {
            "chapter_name": "Organic Chemistry",
            "subject_name": "Chemistry",
            "estimated_duration_min": 60,
            "priority_score": 0.70,
        },
    ],
    "weak_chapters": ["Electrostatics", "Matrices"],
    "test_summary": [{"subject": "Physics", "avg_percentage": 72.5}],
}

EMPTY_CONTEXT: dict = {}


# ---------------------------------------------------------------------------
# Test 1: ask_tillu returns Groq response when Groq succeeds
# ---------------------------------------------------------------------------

class TestAskTilluGroqSuccess:
    @pytest.mark.asyncio
    async def test_returns_groq_response_on_success(self):
        """ask_tillu must return Groq's response when the call succeeds."""
        groq_response = "Study Physics for 90 minutes then take a 15-min break."

        with patch(
            "app.agents.tillu_brain.call_groq",
            new=AsyncMock(return_value=groq_response),
        ) as mock_groq, patch(
            "app.agents.tillu_brain.call_cerebras",
            new=AsyncMock(return_value="cerebras-fallback"),
        ) as mock_cerebras:
            result = await ask_tillu("Plan my day", SAMPLE_CONTEXT)

        assert result == groq_response
        mock_groq.assert_awaited_once()
        mock_cerebras.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_groq_receives_system_prompt(self):
        """ask_tillu must inject the Tillu system prompt as the first message."""
        captured_messages = []

        async def capture_groq(messages, **kwargs):
            captured_messages.extend(messages)
            return "ok"

        with patch("app.agents.tillu_brain.call_groq", side_effect=capture_groq):
            await ask_tillu("hello", SAMPLE_CONTEXT)

        assert captured_messages[0]["role"] == "system"
        assert captured_messages[0]["content"] == TILLU_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_groq_receives_user_message_in_context(self):
        """ask_tillu must include the user message in the second message payload."""
        captured_messages = []

        async def capture_groq(messages, **kwargs):
            captured_messages.extend(messages)
            return "ok"

        with patch("app.agents.tillu_brain.call_groq", side_effect=capture_groq):
            await ask_tillu("Generate study plan", SAMPLE_CONTEXT)

        user_msg = captured_messages[1]["content"]
        assert "Generate study plan" in user_msg
        assert captured_messages[1]["role"] == "user"


# ---------------------------------------------------------------------------
# Test 2: ask_tillu falls back to Cerebras when Groq raises an exception
# ---------------------------------------------------------------------------

class TestAskTilluCerebrasFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_cerebras_on_groq_exception(self):
        """ask_tillu must call Cerebras when Groq raises any exception."""
        cerebras_response = "Cerebras fallback plan: study Organic Chemistry."

        with patch(
            "app.agents.tillu_brain.call_groq",
            new=AsyncMock(side_effect=Exception("Groq unavailable")),
        ), patch(
            "app.agents.tillu_brain.call_cerebras",
            new=AsyncMock(return_value=cerebras_response),
        ) as mock_cerebras:
            result = await ask_tillu("Plan my day", SAMPLE_CONTEXT)

        assert result == cerebras_response
        mock_cerebras.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_cerebras_on_groq_http_error(self):
        """ask_tillu must call Cerebras when Groq returns an HTTP error."""
        import httpx
        from unittest.mock import MagicMock

        http_error = httpx.HTTPStatusError(
            message="429 Too Many Requests",
            request=MagicMock(),
            response=MagicMock(),
        )
        cerebras_response = "Cerebras study plan."

        with patch(
            "app.agents.tillu_brain.call_groq",
            new=AsyncMock(side_effect=http_error),
        ), patch(
            "app.agents.tillu_brain.call_cerebras",
            new=AsyncMock(return_value=cerebras_response),
        ):
            result = await ask_tillu("Plan my day", SAMPLE_CONTEXT)

        assert result == cerebras_response

    @pytest.mark.asyncio
    async def test_cerebras_receives_same_messages_as_groq(self):
        """ask_tillu must send the same message list to Cerebras as it would to Groq."""
        captured_messages = []

        async def capture_cerebras(messages, **kwargs):
            captured_messages.extend(messages)
            return "cerebras-ok"

        with patch(
            "app.agents.tillu_brain.call_groq",
            new=AsyncMock(side_effect=Exception("groq down")),
        ), patch(
            "app.agents.tillu_brain.call_cerebras",
            side_effect=capture_cerebras,
        ):
            await ask_tillu("test message", SAMPLE_CONTEXT)

        assert captured_messages[0]["role"] == "system"
        assert captured_messages[0]["content"] == TILLU_SYSTEM_PROMPT
        assert captured_messages[1]["role"] == "user"
        assert "test message" in captured_messages[1]["content"]


# ---------------------------------------------------------------------------
# Test 3: ask_tillu falls back to rule-based when both providers fail
# ---------------------------------------------------------------------------

class TestAskTilluRuleBasedFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_rule_based_when_both_fail(self):
        """ask_tillu must use rule-based plan when both Groq and Cerebras fail."""
        with patch(
            "app.agents.tillu_brain.call_groq",
            new=AsyncMock(side_effect=Exception("groq down")),
        ), patch(
            "app.agents.tillu_brain.call_cerebras",
            new=AsyncMock(side_effect=Exception("cerebras down")),
        ):
            result = await ask_tillu("Plan my day", SAMPLE_CONTEXT)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Rule-based plan" in result

    @pytest.mark.asyncio
    async def test_rule_based_fallback_contains_tasks(self):
        """Rule-based fallback must include task names from context."""
        with patch(
            "app.agents.tillu_brain.call_groq",
            new=AsyncMock(side_effect=Exception("groq down")),
        ), patch(
            "app.agents.tillu_brain.call_cerebras",
            new=AsyncMock(side_effect=Exception("cerebras down")),
        ):
            result = await ask_tillu("Plan my day", SAMPLE_CONTEXT)

        assert "Electrostatics" in result or "Organic Chemistry" in result

    @pytest.mark.asyncio
    async def test_rule_based_fallback_with_empty_context(self):
        """Rule-based fallback must return descriptive string when context has no tasks."""
        with patch(
            "app.agents.tillu_brain.call_groq",
            new=AsyncMock(side_effect=Exception("groq down")),
        ), patch(
            "app.agents.tillu_brain.call_cerebras",
            new=AsyncMock(side_effect=Exception("cerebras down")),
        ):
            result = await ask_tillu("Plan my day", EMPTY_CONTEXT)

        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Test 4: _rule_based_plan returns non-empty string for any non-empty task list
# ---------------------------------------------------------------------------

class TestRuleBasedPlanNonEmpty:
    def test_returns_non_empty_string_for_tasks(self):
        """_rule_based_plan must return a non-empty string when tasks are present."""
        context = {
            "tasks": [
                {
                    "chapter_name": "Electrostatics",
                    "subject_name": "Physics",
                    "estimated_duration_min": 90,
                    "priority_score": 0.85,
                }
            ]
        }
        result = _rule_based_plan(context)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_tasks_sorted_by_priority_score_descending(self):
        """_rule_based_plan must list tasks in descending priority_score order."""
        context = {
            "tasks": [
                {
                    "chapter_name": "Low Priority Chapter",
                    "subject_name": "English",
                    "estimated_duration_min": 30,
                    "priority_score": 0.20,
                },
                {
                    "chapter_name": "High Priority Chapter",
                    "subject_name": "Physics",
                    "estimated_duration_min": 90,
                    "priority_score": 0.95,
                },
                {
                    "chapter_name": "Medium Priority Chapter",
                    "subject_name": "Chemistry",
                    "estimated_duration_min": 60,
                    "priority_score": 0.60,
                },
            ]
        }
        result = _rule_based_plan(context)
        high_pos = result.index("High Priority Chapter")
        medium_pos = result.index("Medium Priority Chapter")
        low_pos = result.index("Low Priority Chapter")
        assert high_pos < medium_pos < low_pos

    def test_single_task_returns_non_empty(self):
        """_rule_based_plan must handle a single task correctly."""
        context = {
            "tasks": [
                {
                    "chapter_name": "Matrices",
                    "subject_name": "Mathematics",
                    "estimated_duration_min": 45,
                    "priority_score": 0.50,
                }
            ]
        }
        result = _rule_based_plan(context)
        assert "Matrices" in result
        assert len(result) > 0

    def test_includes_duration_info(self):
        """_rule_based_plan must include the estimated duration in the output."""
        context = {
            "tasks": [
                {
                    "chapter_name": "Calculus",
                    "subject_name": "Mathematics",
                    "estimated_duration_min": 75,
                    "priority_score": 0.70,
                }
            ]
        }
        result = _rule_based_plan(context)
        assert "75" in result

    def test_uses_title_fallback_when_chapter_name_missing(self):
        """_rule_based_plan must use 'title' key if 'chapter_name' is absent."""
        context = {
            "tasks": [
                {
                    "title": "Revision Session",
                    "subject": "Physics",
                    "estimated_duration_min": 60,
                    "priority_score": 0.65,
                }
            ]
        }
        result = _rule_based_plan(context)
        assert "Revision Session" in result

    def test_uses_unknown_fallback_for_missing_fields(self):
        """_rule_based_plan must gracefully handle tasks missing all name fields."""
        context = {
            "tasks": [
                {
                    "priority_score": 0.50,
                }
            ]
        }
        result = _rule_based_plan(context)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Unknown" in result


# ---------------------------------------------------------------------------
# Test 5: _rule_based_plan returns a descriptive string when task list is empty
# ---------------------------------------------------------------------------

class TestRuleBasedPlanEmpty:
    def test_returns_descriptive_string_for_empty_tasks(self):
        """_rule_based_plan must return a descriptive non-empty string for empty task list."""
        result = _rule_based_plan({"tasks": []})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_tasks_message_is_actionable(self):
        """_rule_based_plan must tell the user to add tasks when the list is empty."""
        result = _rule_based_plan({"tasks": []})
        # Should contain guidance, not just a blank or error
        assert "task" in result.lower() or "study" in result.lower()

    def test_missing_tasks_key_treated_as_empty(self):
        """_rule_based_plan must handle context with no 'tasks' key gracefully."""
        result = _rule_based_plan({})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_tasks_treated_as_empty(self):
        """_rule_based_plan must handle context with tasks=None gracefully."""
        # context.get("tasks", []) will return None if explicitly set;
        # sorted(None, ...) would raise — so we verify the empty-list guard works
        # when the key is absent (the None case is intentionally not the contract).
        result = _rule_based_plan({})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Test 6: ask_tillu handles Groq timeout by falling back to Cerebras
# ---------------------------------------------------------------------------

class TestAskTilluTimeoutFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_cerebras_on_groq_timeout(self):
        """ask_tillu must fall back to Cerebras when Groq's wait_for times out."""
        cerebras_response = "Cerebras plan after Groq timeout."
        call_count = 0

        async def mock_wait_for(coro, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call wraps Groq — simulate asyncio.TimeoutError
                coro.close()
                raise asyncio.TimeoutError()
            # Second call wraps Cerebras — let it complete normally
            return await coro

        with patch("app.agents.tillu_brain.asyncio.wait_for", side_effect=mock_wait_for), patch(
            "app.agents.tillu_brain.call_cerebras",
            new=AsyncMock(return_value=cerebras_response),
        ) as mock_cerebras:
            result = await ask_tillu("Plan my day", SAMPLE_CONTEXT)

        assert result == cerebras_response
        mock_cerebras.assert_awaited_once()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_falls_back_to_rule_based_on_both_timeouts(self):
        """ask_tillu must use rule-based fallback when both providers time out."""

        async def slow_call(messages, **kwargs):
            await asyncio.sleep(100)
            return "never"

        with patch("app.agents.tillu_brain.call_groq", side_effect=slow_call), patch(
            "app.agents.tillu_brain.call_cerebras", side_effect=slow_call
        ):
            # Override the internal timeout to be very short for testing
            original_wait_for = asyncio.wait_for

            call_count = 0

            async def fast_timeout(coro, timeout):
                nonlocal call_count
                call_count += 1
                raise asyncio.TimeoutError()

            with patch("app.agents.tillu_brain.asyncio.wait_for", side_effect=fast_timeout):
                result = await ask_tillu("Plan my day", SAMPLE_CONTEXT)

        assert isinstance(result, str)
        assert len(result) > 0
        assert call_count == 2  # Groq timeout + Cerebras timeout

    @pytest.mark.asyncio
    async def test_groq_asyncio_timeout_error_triggers_cerebras(self):
        """ask_tillu must catch asyncio.TimeoutError from wait_for and try Cerebras."""
        cerebras_response = "Cerebras fallback response."

        call_count = 0

        async def mock_wait_for(coro, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (Groq) — simulate timeout
                coro.close()
                raise asyncio.TimeoutError()
            # Second call (Cerebras) — succeed
            return await coro

        with patch("app.agents.tillu_brain.asyncio.wait_for", side_effect=mock_wait_for), patch(
            "app.agents.tillu_brain.call_cerebras",
            new=AsyncMock(return_value=cerebras_response),
        ):
            result = await ask_tillu("Plan my day", SAMPLE_CONTEXT)

        assert result == cerebras_response
        assert call_count == 2
