import asyncio
import logging

from supabase import create_client, Client

from app.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    """Return the shared Supabase client, creating it on first call."""
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _client


async def verify_connection(timeout: float = 10.0) -> None:
    """Probe the database to confirm connectivity.

    Queries the ``profiles`` table with a lightweight SELECT.  Raises
    ``RuntimeError`` if the probe times out or any other exception occurs,
    so the caller (lifespan) can abort startup cleanly.
    """
    try:
        async with asyncio.timeout(timeout):
            # Run the synchronous supabase-py call in the default executor so it
            # doesn't block the event loop while still being cancellable via the
            # asyncio timeout.
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: get_client()
                .table("profiles")
                .select("id")
                .limit(1)
                .execute(),
            )
    except TimeoutError as exc:
        raise RuntimeError(
            f"Database connection probe timed out after {timeout}s. "
            "Check SUPABASE_URL and network connectivity."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Database connection probe failed: {exc}. "
            "Check SUPABASE_URL, SUPABASE_ANON_KEY, and network connectivity."
        ) from exc
