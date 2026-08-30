# Design Document — Tillu AI Study OS

## Overview

Tillu AI Study OS is a local-first Windows PC application for a Class 12 CBSE student. A single launcher script starts both a FastAPI backend and a Next.js frontend. All persistent data lives in Supabase cloud (Postgres + pgvector). AI inference is routed through Groq (primary) then Cerebras (fallback), with a deterministic rule-based fallback when both are unavailable. The system coordinates a study coach persona ("Tillu"), daily plan generation, a live dashboard, notifications, and session tracking toward a single mission: complete the CBSE syllabus by 30 November and score 90%+.

---

## System Architecture

```
Student → Browser (localhost:3000)
              ↕  HTTP REST (fetch/axios)
              ↕  WebSocket /ws
         ┌─────────────────────────────────────────────────────┐
         │  FastAPI Backend  (localhost:8000)                  │
         │                                                     │
         │  main.py          ← Uvicorn ASGI entry point        │
         │  config.py        ← pydantic-settings + .env        │
         │  db.py            ← supabase-py client singleton    │
         │  scheduler.py     ← AsyncIOScheduler (APScheduler)  │
         │  websocket_manager.py ← ConnectionManager           │
         │                                                     │
         │  agents/                                            │
         │    tillu_brain.py     (Groq → Cerebras → rule-based)│
         │    planner_agent.py   (nightly plan)                │
         │    reminder_agent.py  (reminder dispatch)           │
         │    sleep_agent.py     (sleep window helpers)        │
         │    quiz_agent.py      (future)                      │
         │    search_agent.py    (Phase 6)                     │
         │                                                     │
         │  providers/                                         │
         │    groq_provider.py                                 │
         │    cerebras_provider.py                             │
         │    sarvam_voice.py    (Phase 4)                     │
         │    parallel_mcp.py    (Phase 6)                     │
         │                                                     │
         │  browser/                                           │
         │    chromium_controller.py  (Phase 3)                │
         │    youtube_player.py       (Phase 3)                │
         │                                                     │
         │  routes/                                            │
         │    tasks.py  · dashboard.py  · voice.py  · chat.py │
         └─────────────────────┬───────────────────────────────┘
                               │ supabase-py
                    ┌──────────▼──────────────┐
                    │  Supabase Cloud          │
                    │  Postgres (11 tables)    │
                    │  pgvector (documents)    │
                    │  Realtime (optional)     │
                    └──────────────────────────┘
```

**Launcher (`start.py`)**
`start.py` (or `run.bat` on Windows) spawns two subprocesses: `uvicorn app.main:app` and `npm run dev --prefix frontend`. It polls `GET /health` in a loop until the backend responds with HTTP 200 (timeout 30 s), then prints the frontend URL and blocks. On `Ctrl+C` (SIGINT), it sends `SIGTERM` to both child processes and waits for them to exit.

---

## Module Designs

### 1. Configuration — `config.py`

Uses `pydantic-settings` to load all settings from `backend/.env`. No secret is hard-coded in source.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    groq_api_key: str
    cerebras_api_key: str
    backend_port: int = 8000
    frontend_port: int = 3000
    frontend_origin: str = "http://localhost:3000"
    scheduler_nightly_hour: int = 22
    scheduler_nightly_minute: int = 0
    default_sleep_start: str = "23:00"
    default_sleep_end: str = "06:00"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

### 2. Database Layer — `db.py`

Exports a single `get_client()` function that returns a shared `supabase.Client` instance. On backend startup, a connection probe runs a lightweight query; if it fails within 10 seconds, the process logs the error and exits with code 1.

```python
from supabase import create_client, Client
from app.config import settings
import asyncio

_client: Client | None = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _client

async def verify_connection(timeout: float = 10.0) -> None:
    """Probe the database; raise RuntimeError on failure."""
    async with asyncio.timeout(timeout):
        get_client().table("profiles").select("id").limit(1).execute()
```

---

### 3. FastAPI Entry Point — `main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.db import verify_connection
from app.scheduler import start_scheduler, stop_scheduler
from app.websocket_manager import ws_manager
from app.routes import tasks, dashboard, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    await verify_connection()      # exits process on failure
    await start_scheduler()
    yield
    await stop_scheduler()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router, prefix="/tasks")
app.include_router(dashboard.router, prefix="/dashboard")
app.include_router(chat.router, prefix="/chat")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket):
    await ws_manager.connect(websocket)
```

Global exception handler returns HTTP 500 with JSON body and logs the full traceback:

```python
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback, logging

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception:\n%s", traceback.format_exc())
    return JSONResponse(status_code=500, content={"error": str(exc)})
```

---

### 4. WebSocket Manager — `websocket_manager.py`

```python
from fastapi import WebSocket
from typing import List
import json

class ConnectionManager:
    def __init__(self):
        self._connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        initial = await self._get_today_tasks()
        await websocket.send_text(json.dumps({"type": "init", "tasks": initial}))
        try:
            while True:
                await websocket.receive_text()   # keep-alive loop
        except Exception:
            self._connections.remove(websocket)

    async def broadcast(self, event: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    async def _get_today_tasks(self) -> list:
        from app.db import get_client
        from datetime import date
        result = get_client().table("study_tasks") \
            .select("*") \
            .eq("scheduled_date", str(date.today())) \
            .order("priority_score", desc=True) \
            .execute()
        return result.data

ws_manager = ConnectionManager()
```

**Event types broadcast over WebSocket:**

| `type` field        | Triggered by                         | Payload fields                          |
|---------------------|--------------------------------------|-----------------------------------------|
| `init`              | Client connects                      | `tasks: []`                             |
| `task_update`       | Task status or score change          | `task_id`, `status`, `priority_score`   |
| `reminder`          | Reminder check job fires             | `reminder_id`, `title`, `scheduled_at`  |
| `daily_plan_created`| Nightly plan job completes           | `date`, `task_count`                    |
| `task_rescheduled`  | Planner reschedules a task           | `task_id`, `new_scheduled_date`         |

---

### 5. APScheduler — `scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings
import logging

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()

async def _safe_run(job_fn, job_name: str):
    try:
        await job_fn()
    except Exception:
        import traceback
        logger.error("Scheduler job %s failed:\n%s", job_name, traceback.format_exc())
        # APScheduler re-fires at next interval automatically

async def start_scheduler():
    from app.agents.planner_agent import run_nightly_plan
    from app.agents.reminder_agent import check_reminders
    from app.agents.planner_agent import check_missed_tasks

    _scheduler.add_job(
        lambda: _safe_run(run_nightly_plan, "nightly_plan"),
        CronTrigger(hour=settings.scheduler_nightly_hour,
                    minute=settings.scheduler_nightly_minute),
        id="nightly_plan",
    )
    _scheduler.add_job(
        lambda: _safe_run(check_reminders, "reminder_check"),
        IntervalTrigger(minutes=5),
        id="reminder_check",
    )
    _scheduler.add_job(
        lambda: _safe_run(check_missed_tasks, "missed_task_check"),
        IntervalTrigger(minutes=30),
        id="missed_task_check",
    )
    _scheduler.start()

async def stop_scheduler():
    _scheduler.shutdown(wait=False)
```

---

### 6. Priority Score Engine

The Priority Score is a pure function. All five input factors must be normalised to `[0.0, 1.0]` before the formula is applied.

```python
from dataclasses import dataclass

@dataclass
class PriorityFactors:
    weakness_score: float        # normalised [0,1]
    deadline_pressure: float     # normalised [0,1]
    board_weightage: float       # normalised [0,1]
    backlog_score: float         # normalised [0,1]
    revision_due_score: float    # normalised [0,1]

def clamp(value: float) -> float:
    """Normalise a raw factor value to [0.0, 1.0]."""
    return max(0.0, min(1.0, float(value)))

def compute_priority_score(factors: PriorityFactors) -> float:
    w  = clamp(factors.weakness_score)
    d  = clamp(factors.deadline_pressure)
    b  = clamp(factors.board_weightage)
    bk = clamp(factors.backlog_score)
    r  = clamp(factors.revision_due_score)
    return round(0.35 * w + 0.25 * d + 0.20 * b + 0.10 * bk + 0.10 * r, 6)
```

**Deadline pressure** is computed from the days remaining until 30 November:

```python
from datetime import date

DEADLINE = date(date.today().year, 11, 30)

def compute_deadline_pressure(scheduled_date: date) -> float:
    days_remaining = (DEADLINE - scheduled_date).days
    if days_remaining <= 0:
        return 1.0
    return clamp(1.0 - days_remaining / 180.0)
```

Priority Score is recomputed and persisted any time a `study_task` is created or any of the five input factors is updated. This is enforced in the task service layer, not at the database level, so the formula remains in one place.

---

### 7. AI Provider Routing — `tillu_brain.py` / `providers/`

```python
import asyncio
from app.providers.groq_provider import call_groq
from app.providers.cerebras_provider import call_cerebras
from app.db import get_client
import logging

logger = logging.getLogger(__name__)

TILLU_SYSTEM_PROMPT = """You are Tillu, a strict but friendly AI study coach for a Class 12 PCM + English + Computer Science board student.
Mission: Help complete syllabus by 30 November and score 90%+.
Always plan using available time, weak chapters, deadline, test scores, and sleep.
Protect sleep schedule. Never suggest distracting activities.
Output must be practical, time-blocked, and specific."""

async def ask_tillu(user_message: str, context: dict) -> str:
    messages = [
        {"role": "system", "content": TILLU_SYSTEM_PROMPT},
        {"role": "user",   "content": _build_context_message(context, user_message)},
    ]
    # Primary: Groq with 15-second timeout
    try:
        return await asyncio.wait_for(call_groq(messages), timeout=15.0)
    except Exception as groq_err:
        logger.warning("Groq failed: %s — falling back to Cerebras", groq_err)
    # Fallback 1: Cerebras
    try:
        return await asyncio.wait_for(call_cerebras(messages), timeout=15.0)
    except Exception as cerebras_err:
        logger.warning("Cerebras failed: %s — using rule-based fallback", cerebras_err)
    # Fallback 2: Rule-based — returns tasks sorted by priority_score
    return _rule_based_plan(context)

def _rule_based_plan(context: dict) -> str:
    tasks = sorted(context.get("tasks", []),
                   key=lambda t: t.get("priority_score", 0), reverse=True)
    if not tasks:
        return "No tasks available. Please add study tasks first."
    lines = [f"{i+1}. {t['chapter_name']} ({t['subject_name']}) — {t['estimated_duration_min']} min"
             for i, t in enumerate(tasks)]
    return "Rule-based plan (AI unavailable):\n" + "\n".join(lines)
```

Both `groq_provider.py` and `cerebras_provider.py` wrap the respective OpenAI-compatible APIs using `httpx.AsyncClient`. Timeout and retry policy is controlled by the caller (`ask_tillu`), not the provider.

---

### 8. Planner Agent — `planner_agent.py`

```python
from datetime import date, datetime, timedelta
from app.db import get_client
from app.agents.tillu_brain import ask_tillu
from app.agents.sleep_agent import get_sleep_window
from app.websocket_manager import ws_manager
import json, logging

logger = logging.getLogger(__name__)

async def run_nightly_plan():
    tomorrow = date.today() + timedelta(days=1)
    db = get_client()

    # Gather context
    sleep_start, sleep_end = await get_sleep_window()
    tasks = db.table("study_tasks").select("*") \
        .eq("status", "pending").execute().data
    weaknesses = await _get_top_mistake_chapters(db)
    test_summary = db.table("tests").select("subject_id, percentage").execute().data

    context = {
        "date": str(tomorrow),
        "sleep_start": sleep_start,
        "sleep_end": sleep_end,
        "tasks": tasks,
        "weak_chapters": weaknesses,
        "test_summary": test_summary,
        "deadline": "2024-11-30",
    }

    plan_text = await ask_tillu("Generate tomorrow's study plan", context)
    scheduled = _parse_and_store_plan(db, plan_text, tomorrow, sleep_start, sleep_end)

    await ws_manager.broadcast({
        "type": "daily_plan_created",
        "date": str(tomorrow),
        "task_count": len(scheduled),
    })

async def check_missed_tasks():
    db = get_client()
    now = datetime.utcnow()
    result = db.table("study_tasks") \
        .select("id, scheduled_date, estimated_duration_min") \
        .eq("status", "pending").execute()
    for task in result.data:
        scheduled_end = _compute_end(task)
        if scheduled_end and scheduled_end < now:
            db.table("study_tasks").update({"status": "missed"}).eq("id", task["id"]).execute()
            await ws_manager.broadcast({"type": "task_update", "task_id": task["id"], "status": "missed"})
```

**Sleep window enforcement:** `_parse_and_store_plan` validates every block against `(sleep_start, sleep_end)` before writing it to `study_tasks`. Blocks that overlap with the sleep window are either trimmed or discarded.

**Available hours budget:** Total available minutes = 24 * 60 − sleep_duration_minutes. No plan may schedule more total task minutes than this budget.

---

### 9. Sleep Agent — `sleep_agent.py`

```python
from datetime import date
from app.db import get_client
from app.config import settings

async def get_sleep_window() -> tuple[str, str]:
    """Return (sleep_start, sleep_end) as HH:MM strings."""
    db = get_client()
    result = db.table("sleep_logs") \
        .select("sleep_start, sleep_end") \
        .eq("log_date", str(date.today())) \
        .order("created_at", desc=True).limit(1).execute()
    if result.data:
        row = result.data[0]
        return row["sleep_start"], row["sleep_end"]
    import logging
    logging.getLogger(__name__).warning("No sleep log for today — using default window")
    return settings.default_sleep_start, settings.default_sleep_end
```

Sleep log validation (enforced in the route handler):

```python
from datetime import datetime
from fastapi import HTTPException

def validate_sleep_log(sleep_start: str, sleep_end: str) -> float:
    fmt = "%H:%M"
    start_dt = datetime.strptime(sleep_start, fmt)
    end_dt   = datetime.strptime(sleep_end, fmt)
    # Handle overnight sleep (end < start means crossing midnight)
    if end_dt <= start_dt:
        end_dt = end_dt.replace(day=end_dt.day + 1)
    duration_hours = (end_dt - start_dt).seconds / 3600.0
    if duration_hours <= 0:
        raise HTTPException(status_code=400,
            detail="sleep_end must be after sleep_start")
    return duration_hours
```

---

### 10. Reminder Agent — `reminder_agent.py`

```python
from datetime import datetime, timedelta
from app.db import get_client
from app.websocket_manager import ws_manager

async def check_reminders():
    db = get_client()
    now = datetime.utcnow()
    window_end = now + timedelta(minutes=5)
    result = db.table("reminders") \
        .select("*") \
        .eq("status", "pending") \
        .gte("scheduled_at", now.isoformat()) \
        .lte("scheduled_at", window_end.isoformat()) \
        .execute()
    for reminder in result.data:
        await _dispatch_reminder(db, reminder)

async def _dispatch_reminder(db, reminder: dict):
    # 1. Windows toast
    _send_toast(reminder["title"], reminder["scheduled_at"])
    # 2. Audio chime
    _play_chime()
    # 3. WebSocket event
    await ws_manager.broadcast({
        "type": "reminder",
        "reminder_id": reminder["id"],
        "title": reminder["title"],
        "scheduled_at": reminder["scheduled_at"],
    })
    # 4. Mark fired — status only transitions pending → fired
    db.table("reminders").update({"status": "fired"}).eq("id", reminder["id"]).execute()

def _send_toast(title: str, scheduled_at: str):
    try:
        from plyer import notification
        notification.notify(title="Tillu Reminder", message=f"{title} at {scheduled_at}", timeout=10)
    except Exception as e:
        import logging; logging.getLogger(__name__).error("Toast failed: %s", e)

def _play_chime():
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load("assets/chime.mp3")
        pygame.mixer.music.play()
    except Exception as e:
        import logging; logging.getLogger(__name__).warning("Audio failed: %s — toast still sent", e)
```

---

### 11. Database Schema

All tables are created via Supabase migration SQL. The `pgvector` extension is enabled first (required before `documents` is created).

```sql
-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- profiles
CREATE TABLE profiles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    target_score NUMERIC(5,2) DEFAULT 90.0,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- subjects
CREATE TABLE subjects (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL   -- Physics, Chemistry, Mathematics, English, Computer Science
);

-- chapters
CREATE TABLE chapters (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id       UUID REFERENCES subjects(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    board_weightage  NUMERIC(5,2) NOT NULL,  -- percentage, raw value before normalisation
    is_completed     BOOLEAN DEFAULT FALSE,
    weakness_score   NUMERIC(5,4) DEFAULT 0.5  -- normalised [0,1]
);

-- study_tasks
CREATE TABLE study_tasks (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id            UUID REFERENCES subjects(id),
    chapter_id            UUID REFERENCES chapters(id),
    scheduled_date        DATE NOT NULL,
    estimated_duration_min INT NOT NULL,
    actual_duration_min   INT DEFAULT 0,
    status                TEXT DEFAULT 'pending'
                          CHECK (status IN ('pending','in-progress','completed','missed')),
    priority_score        NUMERIC(8,6) NOT NULL DEFAULT 0.0,
    created_at            TIMESTAMPTZ DEFAULT now()
);

-- study_sessions
CREATE TABLE study_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID REFERENCES study_tasks(id) ON DELETE CASCADE,
    started_at  TIMESTAMPTZ NOT NULL,
    ended_at    TIMESTAMPTZ,
    duration_min INT,
    status      TEXT DEFAULT 'active' CHECK (status IN ('active','completed'))
);

-- sleep_logs
CREATE TABLE sleep_logs (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id            UUID REFERENCES profiles(id),
    log_date              DATE NOT NULL,
    sleep_start           TIME NOT NULL,
    sleep_end             TIME NOT NULL,
    total_sleep_hours     NUMERIC(4,2) NOT NULL,
    created_at            TIMESTAMPTZ DEFAULT now()
);

-- mistakes
CREATE TABLE mistakes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id       UUID REFERENCES profiles(id),
    subject_id       UUID REFERENCES subjects(id),
    chapter_id       UUID REFERENCES chapters(id),
    description      TEXT NOT NULL,
    recurrence_count INT DEFAULT 1,
    created_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (profile_id, subject_id, chapter_id, description)
);

-- tests
CREATE TABLE tests (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id  UUID REFERENCES profiles(id),
    subject_id  UUID REFERENCES subjects(id),
    chapter_id  UUID REFERENCES chapters(id),
    score       NUMERIC(6,2) NOT NULL CHECK (score >= 0),
    max_score   NUMERIC(6,2) NOT NULL CHECK (max_score > 0),
    percentage  NUMERIC(5,2) GENERATED ALWAYS AS (score / max_score * 100) STORED,
    taken_at    TIMESTAMPTZ DEFAULT now()
);

-- reminders
CREATE TABLE reminders (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id   UUID REFERENCES profiles(id),
    title        TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    status       TEXT DEFAULT 'pending' CHECK (status IN ('pending','fired'))
);

-- playlists
CREATE TABLE playlists (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id   UUID REFERENCES subjects(id),
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    watch_status TEXT DEFAULT 'unwatched' CHECK (watch_status IN ('unwatched','watched'))
);

-- documents (Phase 6 — pgvector)
CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id  UUID REFERENCES subjects(id),
    filename    TEXT NOT NULL,
    chunk_text  TEXT NOT NULL,
    embedding   vector(384),
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

---

### 12. REST API Routes

| Method | Path                    | Description                                           |
|--------|-------------------------|-------------------------------------------------------|
| GET    | `/health`               | Liveness probe                                        |
| GET    | `/tasks/today`          | Today's tasks sorted by priority_score desc           |
| PATCH  | `/tasks/{id}/status`    | Update task status; triggers WS broadcast             |
| POST   | `/tasks/{id}/session/start` | Create study session record                       |
| POST   | `/tasks/{id}/session/stop`  | Close session, compute duration, update actual_min|
| GET    | `/sessions/today`       | All sessions for today                                |
| GET    | `/chapters`             | Chapters filtered by `?subject_id=`                   |
| PATCH  | `/chapters/{id}/complete` | Mark chapter completed, zero weakness_score         |
| POST   | `/sleep-logs`           | Store sleep log (validates end > start)               |
| POST   | `/mistakes`             | Store mistake, increment recurrence if duplicate      |
| GET    | `/mistakes`             | Mistakes grouped by subject/chapter, sorted by count  |
| POST   | `/tests`                | Store test score (validates 0 ≤ score ≤ max_score)    |
| GET    | `/tests/summary`        | Per-subject average percentage scores                 |
| POST   | `/reminders`            | Create reminder with status=pending                   |
| GET    | `/reminders`            | Today's reminders with status                         |
| POST   | `/chat`                 | Send message to Tillu, receive AI response            |
| WS     | `/ws`                   | WebSocket live update stream                          |

---

### 13. Frontend Architecture

#### Pages (Next.js App Router)

**`app/page.tsx` — Home Dashboard**
- Fetches today's tasks from `GET /tasks/today` on mount.
- Renders `<TaskCard>` per task, sorted by `priority_score` (desc).
- Each `TaskCard` shows subject, chapter, status badge, duration, priority bar, and Start/Stop/Complete controls.
- On mark-complete: `PATCH /tasks/{id}/status` → optimistic UI update.
- WebSocket updates via `useWebSocket` hook in `lib/socket.ts`.

**`app/timetable/page.tsx`**
- Displays the current week in a 7-column calendar grid.
- Study blocks shown as coloured tiles (colour per subject).
- Data from `GET /tasks/today` + tasks for adjacent days.

**`app/syllabus/page.tsx`**
- Accordion per subject, expanding to list chapters.
- Each chapter row: name, board weightage %, completion toggle, weakness indicator.
- Per-subject completion % from `GET /chapters?subject_id=X` (completed / total).
- Associated playlists listed per subject (Phase 3).

#### Components

```
components/
├── TaskCard.tsx          — task status badge, priority bar, session controls
├── NotificationBanner.tsx — dismissable banner rendered on WS reminder/missed events
├── SyllabusProgress.tsx  — circular progress ring per subject
└── TilluChat.tsx         — chat input + scrollable message thread
```

#### WebSocket Client — `lib/socket.ts`

```typescript
const BASE_DELAY = 1000;
const MAX_DELAY = 30000;

export function createWebSocketClient(
  onMessage: (event: MessageEvent) => void
): () => void {
  let ws: WebSocket | null = null;
  let delay = BASE_DELAY;
  let stopped = false;

  function connect() {
    ws = new WebSocket("ws://localhost:8000/ws");
    ws.onmessage = onMessage;
    ws.onopen = () => { delay = BASE_DELAY; };
    ws.onclose = () => {
      if (!stopped) {
        setTimeout(connect, delay);
        delay = Math.min(delay * 2, MAX_DELAY);
      }
    };
  }

  connect();
  return () => { stopped = true; ws?.close(); };
}
```

Reconnection uses exponential back-off: 1 s → 2 s → 4 s … capped at 30 s.

#### State Management

React context (`StudyContext`) holds today's tasks and notification state. The WebSocket `useEffect` hook dispatches `task_update`, `reminder`, and `daily_plan_created` events into the context reducer. No external state library is required at this scale.

---

### 14. Notification System

Three channels fire together whenever a reminder dispatches or a task is marked `missed`:

| Channel | Library | Failure handling |
|---------|---------|-----------------|
| Windows toast | `plyer` (`notification.notify`) | Log error; continue |
| Audio chime | `pygame.mixer` | Log warning; continue |
| Dashboard Visual Alert | WebSocket JSON event → `<NotificationBanner>` | N/A (in-process) |

The `_dispatch_reminder` function calls all three sequentially; any individual failure is caught and logged without aborting the others. The Dashboard Visual Alert remains visible until the student clicks its dismiss button or navigates away, enforced by component state.

---

### 15. Mistake Tracking — Upsert Logic

```python
async def store_mistake(profile_id: str, subject_id: str,
                        chapter_id: str, description: str) -> dict:
    db = get_client()
    # Try to find existing identical mistake
    existing = db.table("mistakes").select("id, recurrence_count") \
        .eq("profile_id", profile_id) \
        .eq("subject_id", subject_id) \
        .eq("chapter_id", chapter_id) \
        .eq("description", description) \
        .execute().data
    if existing:
        row = existing[0]
        new_count = row["recurrence_count"] + 1
        db.table("mistakes").update({"recurrence_count": new_count}) \
            .eq("id", row["id"]).execute()
        return {**row, "recurrence_count": new_count}
    return db.table("mistakes").insert({
        "profile_id": profile_id, "subject_id": subject_id,
        "chapter_id": chapter_id, "description": description,
        "recurrence_count": 1,
    }).execute().data[0]
```

The `/mistakes` GET endpoint groups results by `subject_id, chapter_id` and sorts by `recurrence_count` descending. The planner reads the top 10 chapters by total recurrence and applies a proportional weakness boost.

---

### 16. Test Score Validation

```python
from fastapi import HTTPException

def validate_test_score(score: float, max_score: float) -> None:
    if score < 0 or score > max_score:
        raise HTTPException(
            status_code=400,
            detail=f"Score must be between 0 and {max_score}. Got {score}."
        )
    if max_score <= 0:
        raise HTTPException(status_code=400, detail="max_score must be greater than 0.")
```

Percentage is stored as a generated column in Postgres (`score / max_score * 100`). The `/tests/summary` endpoint aggregates with `AVG(percentage)` grouped by `subject_id`.

---

### 17. Phase 3+ Extension Points

| Phase | Feature | Entry point | Toggle |
|-------|---------|------------|--------|
| 3 | Playlist / YouTube via Playwright | `browser/chromium_controller.py` | `PLAYWRIGHT_ENABLED=true` env var |
| 4 | Voice (Sarvam STT/TTS) | `providers/sarvam_voice.py`, `routes/voice.py` | `SARVAM_ENABLED=true` |
| 6 | RAG + Parallel MCP | `providers/parallel_mcp.py`, `agents/search_agent.py` | `RAG_ENABLED=true` |

Each feature flag is read from `config.py`. Routes and agents for disabled phases are imported but return `HTTP 503 Feature not enabled` responses until the feature is activated.

---

### 18. Error Handling Summary

| Scenario | Behaviour |
|----------|-----------|
| Supabase unreachable at startup | Backend logs error, exits with code 1 |
| Groq timeout (15 s) | Retry with Cerebras |
| Groq + Cerebras both fail | Rule-based priority sort; fallback logged |
| Scheduler job exception | Error logged with traceback; job rescheduled at next interval |
| Audio output unavailable | Warning logged; toast + WebSocket event still fire |
| Invalid sleep log (end ≤ start) | HTTP 400 with descriptive message |
| Invalid test score (out of range) | HTTP 400 with descriptive message |
| Unhandled route exception | HTTP 500 + JSON body + full traceback logged |
| WebSocket client disconnect | Connection silently removed from registry |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Priority Score Bounded Output

*For any* five input factors where each is a real number (unclamped), `compute_priority_score` SHALL return a value in the closed interval `[0.0, 1.0]` after normalisation.

**Validates: Requirements 5.1, 5.4**

---

### Property 2: Priority Score Formula Correctness

*For any* five input factors already normalised to `[0.0, 1.0]`, the computed priority score SHALL equal exactly `0.35 × weakness + 0.25 × deadline_pressure + 0.20 × board_weightage + 0.10 × backlog_score + 0.10 × revision_due_score` (to floating-point precision).

**Validates: Requirements 5.1**

---

### Property 3: Priority Score Persistence Round-Trip

*For any* valid study task creation payload, the priority score stored in `study_tasks` SHALL equal the value returned by `compute_priority_score` applied to the same input factors.

**Validates: Requirements 5.2, 5.3**

---

### Property 4: Nightly Plan Respects Sleep Window

*For any* sleep window `(sleep_start, sleep_end)` and any set of study tasks, no task block in the generated nightly plan SHALL overlap with the student's sleep window.

**Validates: Requirements 9.5**

---

### Property 5: Nightly Plan Does Not Exceed Available Hours

*For any* student sleep window, the sum of estimated durations of all tasks scheduled in the nightly plan SHALL not exceed the available waking hours (24h minus sleep duration).

**Validates: Requirements 9.6**

---

### Property 6: Rule-Based Fallback Always Produces a Plan

*For any* non-empty set of study tasks, the rule-based fallback in `_rule_based_plan` SHALL return a non-empty string containing at least one task entry.

**Validates: Requirements 9.3**

---

### Property 7: Sleep Log Validation Rejects Invalid Intervals

*For any* pair `(sleep_start, sleep_end)` where `sleep_end` is not strictly after `sleep_start` (accounting for overnight crossings), the backend SHALL return HTTP 400.

**Validates: Requirements 10.2**

---

### Property 8: Sleep Log Duration Computation

*For any* valid `(sleep_start, sleep_end)` pair, the stored `total_sleep_hours` SHALL equal `(sleep_end − sleep_start)` converted to hours (with overnight handling).

**Validates: Requirements 10.3**

---

### Property 9: Mistake Recurrence Counting

*For any* `(profile_id, subject_id, chapter_id, description)` tuple submitted `N` times (N ≥ 1), the `recurrence_count` in the `mistakes` table SHALL equal `N`.

**Validates: Requirements 11.2**

---

### Property 10: Mistakes Endpoint Sort Order

*For any* set of mistake records with varying recurrence counts, the `/mistakes` GET response SHALL list records in non-increasing order of `recurrence_count`.

**Validates: Requirements 11.3**

---

### Property 11: Test Score Validation Rejects Out-of-Range Values

*For any* `(score, max_score)` pair where `score < 0` or `score > max_score`, the backend SHALL return HTTP 400.

**Validates: Requirements 12.2**

---

### Property 12: Test Score Percentage Computation

*For any* valid `(score, max_score)` pair (score ∈ [0, max_score], max_score > 0), the stored `percentage` SHALL equal `(score / max_score) × 100`.

**Validates: Requirements 12.3**

---

### Property 13: Test Summary Average Correctness

*For any* set of test records grouped by subject, the `/tests/summary` average percentage for that subject SHALL equal the arithmetic mean of all individual `percentage` values for that subject.

**Validates: Requirements 12.4**

---

### Property 14: WebSocket Broadcast Completeness

*For any* set of N connected WebSocket clients and any broadcast event (task_update, reminder, daily_plan_created), all N clients SHALL receive the event; clients that disconnect mid-broadcast SHALL be removed without affecting the remaining clients.

**Validates: Requirements 7.3, 7.4, 7.5**

---

### Property 15: Reminder Status Is Monotone

*For any* reminder record, the status transition SHALL only move from `pending` to `fired` and SHALL never revert to `pending` after being set to `fired`.

**Validates: Requirements 14.4**

---

### Property 16: Study Session Actual Duration Accumulation

*For any* study task with K completed sessions, the `actual_duration_min` stored on the task SHALL equal the sum of `duration_min` across all K completed `study_sessions` records for that task.

**Validates: Requirements 15.4**

---

### Property 17: Chapter Completion Zeroes Weakness Score

*For any* chapter, marking it as completed via `PATCH /chapters/{id}/complete` SHALL set its `weakness_score` to `0.0` and SHALL preserve this invariant in all subsequent Priority Score computations that reference that chapter.

**Validates: Requirements 13.4**

---

### Property 18: Syllabus Completion Percentage Accuracy

*For any* subject with `T` total chapters and `C` completed chapters, the displayed completion percentage SHALL equal `(C / T) × 100` (rounded to one decimal place).

**Validates: Requirements 13.5**
