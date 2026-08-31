"""Cerebras inference provider — OpenAI-compatible API.

Uses httpx.AsyncClient to call the Cerebras chat completions endpoint.
Timeout and retry policy are handled by the CALLER (tillu_brain.py).
This module just surfaces exceptions.
"""

import httpx
from app.config import settings

CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
CEREBRAS_DEFAULT_MODEL = "llama3.1-8b"


async def call_cerebras(
    messages: list[dict],
    model: str = CEREBRAS_DEFAULT_MODEL,
) -> str:
    """Call Cerebras chat completions and return the assistant message content.

    Args:
        messages: List of {"role": ..., "content": ...} dicts.
        model: Cerebras model ID.

    Returns:
        The assistant's text response.

    Raises:
        httpx.HTTPStatusError: on non-2xx response.
        httpx.TimeoutException: on timeout (caller handles this).
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{CEREBRAS_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.cerebras_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.3,
            },
            timeout=30.0,  # Caller wraps in asyncio.wait_for with 15s anyway
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
