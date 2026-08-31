"""Chromium browser controller for Playwright-based automation.

This module manages a singleton Playwright Chromium browser context.
It is only imported / used when ``PLAYWRIGHT_ENABLED=true`` is set in the
environment.  If the ``playwright`` package is not installed a clear
``ImportError`` is raised with installation instructions.

Usage::

    async with chromium_session() as context:
        page = await context.new_page()
        await page.goto("https://www.youtube.com/playlist?list=...")
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import — playwright is an optional dependency
# ---------------------------------------------------------------------------

try:
    from playwright.async_api import (
        async_playwright,
        Browser,
        BrowserContext,
        Playwright,
    )
    _PLAYWRIGHT_PACKAGE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PLAYWRIGHT_PACKAGE_AVAILABLE = False

    # Provide stubs so the rest of the module can be parsed even when
    # playwright is absent.  Runtime calls will raise before reaching code
    # that uses these names because of the availability check in
    # `launch_browser`.
    Browser = object  # type: ignore[assignment,misc]
    BrowserContext = object  # type: ignore[assignment,misc]
    Playwright = object  # type: ignore[assignment,misc]


def _require_playwright() -> None:
    """Raise a helpful ``ImportError`` when playwright is not installed."""
    if not _PLAYWRIGHT_PACKAGE_AVAILABLE:
        raise ImportError(
            "The 'playwright' package is required for Chromium automation but is "
            "not installed.  Install it and the browser binaries with:\n"
            "  pip install playwright==1.44.0\n"
            "  playwright install chromium"
        )


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

async def launch_browser() -> "BrowserContext":
    """Launch a non-headless Chromium browser and return a ``BrowserContext``.

    The returned context is owned by the caller; close it with
    :func:`close_browser` when finished.

    Raises
    ------
    ImportError
        If the ``playwright`` package is not installed.
    """
    _require_playwright()
    from playwright.async_api import async_playwright  # local import for type safety

    logger.info("Launching Chromium browser via Playwright…")
    pw: Playwright = await async_playwright().start()
    browser: Browser = await pw.chromium.launch(headless=False)
    context: BrowserContext = await browser.new_context()
    # Stash the playwright instance on the context so we can stop it later.
    context._tillu_playwright = pw  # type: ignore[attr-defined]
    context._tillu_browser = browser  # type: ignore[attr-defined]
    logger.info("Chromium browser launched successfully.")
    return context


async def close_browser(context: "BrowserContext") -> None:
    """Close a ``BrowserContext`` (and its parent browser + Playwright instance).

    Parameters
    ----------
    context:
        The context returned by :func:`launch_browser`.
    """
    _require_playwright()
    logger.info("Closing Chromium browser…")
    try:
        await context.close()
        browser = getattr(context, "_tillu_browser", None)
        if browser is not None:
            await browser.close()
        pw = getattr(context, "_tillu_playwright", None)
        if pw is not None:
            await pw.stop()
        logger.info("Chromium browser closed.")
    except Exception:
        logger.exception("Error while closing Chromium browser — ignored.")


# ---------------------------------------------------------------------------
# Context manager (recommended usage)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def chromium_session() -> AsyncGenerator["BrowserContext", None]:
    """Async context manager that yields a ``BrowserContext``.

    Guarantees the browser is closed even if an exception occurs::

        async with chromium_session() as ctx:
            page = await ctx.new_page()
            await page.goto(url)
    """
    context = await launch_browser()
    try:
        yield context
    finally:
        await close_browser(context)
