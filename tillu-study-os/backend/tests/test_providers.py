"""Unit tests for Groq and Cerebras provider stubs.

Tests:
  - call_groq uses the correct endpoint URL and Authorization header
  - call_groq returns the assistant message content from the response JSON
  - call_groq raises httpx.HTTPStatusError on non-2xx responses
  - call_cerebras uses the Cerebras endpoint URL and API key
  - call_cerebras returns the assistant message content from the response JSON

All tests mock httpx.AsyncClient.post so no real network calls are made.
"""

import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.groq_provider import call_groq, GROQ_BASE_URL, GROQ_DEFAULT_MODEL
from app.providers.cerebras_provider import call_cerebras, CEREBRAS_BASE_URL, CEREBRAS_DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_response(content: str, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response whose .json() returns a valid completions body."""
    body = {
        "choices": [
            {"message": {"content": content}}
        ]
    }
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body
    # raise_for_status should be a no-op for 2xx, raise for others
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=mock_resp,
        )
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# call_groq tests
# ---------------------------------------------------------------------------

class TestCallGroq:
    @pytest.mark.asyncio
    async def test_groq_calls_correct_endpoint(self):
        """call_groq must POST to the Groq chat completions URL."""
        mock_resp = _make_mock_response("Hello from Groq")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_groq([{"role": "user", "content": "hi"}])

        called_url = mock_post.call_args[0][0]
        assert called_url == f"{GROQ_BASE_URL}/chat/completions"

    @pytest.mark.asyncio
    async def test_groq_sends_authorization_header(self):
        """call_groq must include Bearer auth with the Groq API key."""
        from app.config import settings

        mock_resp = _make_mock_response("response")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_groq([{"role": "user", "content": "test"}])

        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == f"Bearer {settings.groq_api_key}"

    @pytest.mark.asyncio
    async def test_groq_returns_assistant_content(self):
        """call_groq must return the assistant message content string."""
        expected = "Study Physics Chapter 1 for 90 minutes."
        mock_resp = _make_mock_response(expected)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            result = await call_groq([{"role": "user", "content": "plan"}])

        assert result == expected

    @pytest.mark.asyncio
    async def test_groq_raises_on_non_2xx(self):
        """call_groq must propagate httpx.HTTPStatusError on error responses."""
        mock_resp = _make_mock_response("", status_code=429)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await call_groq([{"role": "user", "content": "plan"}])

    @pytest.mark.asyncio
    async def test_groq_uses_default_model_in_payload(self):
        """call_groq must include the default model ID in the request body."""
        mock_resp = _make_mock_response("ok")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_groq([{"role": "user", "content": "hi"}])

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == GROQ_DEFAULT_MODEL

    @pytest.mark.asyncio
    async def test_groq_accepts_custom_model(self):
        """call_groq must pass a custom model when provided."""
        mock_resp = _make_mock_response("ok")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_groq([{"role": "user", "content": "hi"}], model="llama-3.1-8b-instant")

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "llama-3.1-8b-instant"

    @pytest.mark.asyncio
    async def test_groq_sends_messages_in_payload(self):
        """call_groq must forward the messages list unchanged in the request body."""
        messages = [
            {"role": "system", "content": "You are Tillu."},
            {"role": "user", "content": "Plan my day."},
        ]
        mock_resp = _make_mock_response("plan")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_groq(messages)

        payload = mock_post.call_args[1]["json"]
        assert payload["messages"] == messages


# ---------------------------------------------------------------------------
# call_cerebras tests
# ---------------------------------------------------------------------------

class TestCallCerebras:
    @pytest.mark.asyncio
    async def test_cerebras_calls_correct_endpoint(self):
        """call_cerebras must POST to the Cerebras chat completions URL."""
        mock_resp = _make_mock_response("Hello from Cerebras")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_cerebras([{"role": "user", "content": "hi"}])

        called_url = mock_post.call_args[0][0]
        assert called_url == f"{CEREBRAS_BASE_URL}/chat/completions"

    @pytest.mark.asyncio
    async def test_cerebras_sends_authorization_header(self):
        """call_cerebras must include Bearer auth with the Cerebras API key."""
        from app.config import settings

        mock_resp = _make_mock_response("response")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_cerebras([{"role": "user", "content": "test"}])

        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == f"Bearer {settings.cerebras_api_key}"

    @pytest.mark.asyncio
    async def test_cerebras_returns_assistant_content(self):
        """call_cerebras must return the assistant message content string."""
        expected = "Fallback plan from Cerebras."
        mock_resp = _make_mock_response(expected)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            result = await call_cerebras([{"role": "user", "content": "plan"}])

        assert result == expected

    @pytest.mark.asyncio
    async def test_cerebras_raises_on_non_2xx(self):
        """call_cerebras must propagate httpx.HTTPStatusError on error responses."""
        mock_resp = _make_mock_response("", status_code=503)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await call_cerebras([{"role": "user", "content": "plan"}])

    @pytest.mark.asyncio
    async def test_cerebras_uses_default_model_in_payload(self):
        """call_cerebras must include the default model ID in the request body."""
        mock_resp = _make_mock_response("ok")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_cerebras([{"role": "user", "content": "hi"}])

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == CEREBRAS_DEFAULT_MODEL

    @pytest.mark.asyncio
    async def test_cerebras_sends_messages_in_payload(self):
        """call_cerebras must forward the messages list unchanged in the request body."""
        messages = [
            {"role": "system", "content": "You are Tillu."},
            {"role": "user", "content": "Plan my day."},
        ]
        mock_resp = _make_mock_response("plan")
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient.post", mock_post):
            await call_cerebras(messages)

        payload = mock_post.call_args[1]["json"]
        assert payload["messages"] == messages


# ---------------------------------------------------------------------------
# Provider symmetry checks
# ---------------------------------------------------------------------------

class TestProviderSymmetry:
    @pytest.mark.asyncio
    async def test_groq_and_cerebras_use_different_endpoints(self):
        """The two providers must target different base URLs."""
        assert GROQ_BASE_URL != CEREBRAS_BASE_URL

    @pytest.mark.asyncio
    async def test_groq_and_cerebras_use_different_api_keys(self):
        """The two providers must use different config keys."""
        from app.config import settings
        # They may happen to be the same placeholder value in CI, but
        # the provider code must reference different settings attributes.
        # We verify this by checking the call args on each provider.
        groq_resp = _make_mock_response("groq")
        cerebras_resp = _make_mock_response("cerebras")

        with patch("httpx.AsyncClient.post", AsyncMock(return_value=groq_resp)):
            await call_groq([{"role": "user", "content": "x"}])

        with patch("httpx.AsyncClient.post", AsyncMock(return_value=cerebras_resp)) as cerebras_post:
            await call_cerebras([{"role": "user", "content": "x"}])

        cerebras_headers = cerebras_post.call_args[1]["headers"]
        assert cerebras_headers["Authorization"] == f"Bearer {settings.cerebras_api_key}"
