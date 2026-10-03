"""Persistence boundary for TILLU.

Development and tests use SQLite. Production is deliberately fail-closed and uses
Supabase Postgres only. Route code imports this module, never a concrete store.
"""
from .config import settings

if settings.environment == "production":
    from .supabase_repository import *  # noqa: F401,F403
else:
    from .database import *  # noqa: F401,F403
