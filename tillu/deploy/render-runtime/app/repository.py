"""Persistence boundary for TILLU.

Development and tests use SQLite. Production brain uses Supabase Postgres.
Runtime always uses SQLite — it is a stateless execution sandbox and does
not own user data. Only the brain service needs Supabase persistence.
"""
from .config import settings

if settings.environment == "production" and settings.service_role != "runtime":
    from .supabase_repository import *  # noqa: F401,F403
else:
    from .database import *  # noqa: F401,F403
