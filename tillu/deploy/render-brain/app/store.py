from uuid import uuid4
from .models import Job

JOBS: dict[str, Job] = {}
PROGRESS: dict[str, dict] = {}

def new_id(prefix: str) -> str:
    # UUIDs remain portable across SQLite and Supabase/Postgres schemas.
    return str(uuid4())
