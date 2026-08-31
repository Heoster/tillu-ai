"""Parallel Search MCP provider — Phase 6 stub.

This module provides a stub for the Parallel Search MCP tool.  It is gated
behind ``PARALLEL_MCP_ENABLED=true`` in the environment.

When the flag is enabled the stub raises ``NotImplementedError``, signalling
that the MCP server endpoint still needs to be configured.  This design
allows the rest of the RAG pipeline to function (document search still
works) while making the integration point clear.

Usage::

    from app.providers.parallel_mcp import parallel_web_search

    results = await parallel_web_search("CBSE Class 12 Newton's laws")
    # returns list of {"title": str, "url": str, "snippet": str}
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


async def parallel_web_search(
    query: str,
    num_results: int = 5,
) -> list[dict]:
    """Stub for the Parallel Search MCP tool.

    When enabled, this would call the configured MCP server to retrieve live
    web search results and return them alongside RAG document chunks when
    composing the Tillu prompt context.

    Args:
        query: Search query string.
        num_results: Desired number of web results (default 5).

    Returns:
        List of ``{"title": str, "url": str, "snippet": str}`` dicts.

    Raises:
        HTTPException(503): when ``PARALLEL_MCP_ENABLED`` is ``false``.
        NotImplementedError: when enabled but the MCP server is not yet
            configured (stub behaviour — replace with real implementation).
    """
    if not settings.parallel_mcp_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "Parallel MCP search is disabled. "
                "Set PARALLEL_MCP_ENABLED=true to enable."
            ),
        )

    # ---------------------------------------------------------------------------
    # TODO: Replace this stub with a real MCP server call.
    #
    # Example implementation sketch (not active):
    #
    #   async with httpx.AsyncClient() as client:
    #       response = await client.post(
    #           MCP_SERVER_URL + "/search",
    #           json={"query": query, "num_results": num_results},
    #           headers={"Authorization": f"Bearer {settings.mcp_api_key}"},
    #           timeout=10.0,
    #       )
    #       response.raise_for_status()
    #       return response.json()["results"]
    # ---------------------------------------------------------------------------

    logger.error(
        "parallel_web_search called but MCP server is not configured. "
        "Implement the MCP server integration in providers/parallel_mcp.py."
    )
    raise NotImplementedError(
        "Parallel MCP server integration not yet configured. "
        "Please set up the MCP server endpoint and update "
        "app/providers/parallel_mcp.py with the real implementation."
    )
