"""YouTube playlist opener using Playwright Chromium.

Provides a simple async API to open a YouTube playlist URL in a visible
Chromium browser window on the student's PC.

The module checks both:
  1. ``settings.playwright_enabled`` — the feature-flag in ``.env``.
  2. Whether the ``playwright`` package is actually importable.

If either condition is not satisfied, :func:`open_playlist` raises
``RuntimeError``; callers (the route handler) convert this into HTTP 503.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def is_playwright_available() -> bool:
    """Return ``True`` when Playwright is both enabled and importable.

    This is a synchronous utility so it can be called from route guards
    without awaiting.

    Returns
    -------
    bool
        ``True``  — ``PLAYWRIGHT_ENABLED=true`` **and** package installed.
        ``False`` — feature disabled or package missing.
    """
    if not settings.playwright_enabled:
        return False
    try:
        import playwright  # noqa: F401  — just checking availability
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Core action
# ---------------------------------------------------------------------------

async def open_playlist(url: str) -> None:
    """Open *url* in a new Chromium page.

    A fresh browser context is created for each call so that multiple
    playlists can be opened in separate windows without state leaking
    between them.

    Parameters
    ----------
    url:
        Full YouTube playlist URL, e.g.
        ``https://www.youtube.com/playlist?list=PLxxxxxxxx``.

    Raises
    ------
    RuntimeError
        When Playwright is disabled (``PLAYWRIGHT_ENABLED`` is falsy) or
        when the ``playwright`` package is not installed.
    """
    if not settings.playwright_enabled:
        raise RuntimeError(
            "Playwright is not enabled. Set PLAYWRIGHT_ENABLED=true in .env "
            "and run 'playwright install chromium'."
        )

    # Import here so the module is importable even without playwright installed.
    try:
        from app.browser.chromium_controller import chromium_session
    except ImportError as exc:
        raise RuntimeError(str(exc)) from exc

    logger.info("Opening YouTube playlist: %s", url)
    async with chromium_session() as context:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        logger.info("Playlist page loaded: %s", url)
        # Keep the page open — the browser window stays visible until the
        # student closes it manually.  We do not await further navigation so
        # the HTTP response is returned promptly.
