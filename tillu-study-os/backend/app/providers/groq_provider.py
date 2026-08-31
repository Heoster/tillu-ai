"""Groq inference provider — OpenAI-compatible API.

Uses httpx.AsyncClient to call the Groq chat completions endpoint.
Timeout and retry policy are handled by the CALLER (tillu_brain.py).
This module just surfaces exceptions.
"""

import httpx
from app.config import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"


async def call_groq(
    messages: list[dict],
    model: str = GROQ_DEFAULT_MODEL,
) -> str:
    """Call Groq chat completions and return the assistant message content.

    Args:
        messages: List of {"role": ..., "content": ...} dicts.
        model: Groq model ID.

    Returns:
        The assistant's text response.

    Raises:
        httpx.HTTPStatusError: on non-2xx response.
        httpx.TimeoutException: on timeout (caller handles this).
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
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
