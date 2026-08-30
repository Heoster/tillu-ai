# Implementation Plan: Tillu AI Study OS — Phase 1 MVP

## Overview

Incremental build of the full Phase 1 MVP: project scaffold → database schema → backend core → priority engine → scheduler + WebSocket → frontend shell → notification system → data entry forms → launcher script. Property-based tests (pytest + hypothesis) are included as optional sub-tasks under each functional area. Phase 2–6 items appear at the end as optional/future tasks.

---

## Tasks

- [x] 1. Project scaffolding — folder structure, dependency files, and environment config
  - [x] 1.1 Create backend directory structure
    - Create `backend/` with sub-packages: `app/`, `app/agents/`, `app/providers/`, `app/browser/`, `app/routes/`
    - Add `__init__.py` to every package directory
    - Create `backend/requirements.txt` pinning: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `supabase`, `apscheduler`, `httpx`, `plyer`, `pygame`, `pytest`, `hypothesis`
    - _Requirements: 3.3_
  - [x] 1.2 Create frontend directory structure
    - Scaffold Next.js 14 App Router project in `frontend/` with TypeScript, Tailwind CSS, and shadcn/ui initialised
    - Create `frontend/lib/` and `frontend/components/` directories
    - _Requirements: 4.4_
  - [x] 1.3 Create environment config files
    - Create `backend/.env.example` with all required keys: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `BACKEND_PORT`, `FRONTEND_PORT`, `FRONTEND_ORIGIN`, `SCHEDULER_NIGHTLY_HOUR`, `SCHEDULER_NIGHTLY_MINUTE`, `DEFAULT_SLEEP_START`, `DEFAULT_SLEEP_END`
    - Create `backend/.env` (gitignored) from the example template
    - Add `.env` to `.gitignore`
    - _Requirements: 3.2_
  - [x] 1.4 Implement `config.py` using pydantic-settings
    - Write `backend/app/config.py` with `Settings` class loading all values from `.env`
    - Export a `settings` singleton
    - _Requirements: 3.1, 3.2_

- [x] 2. Supabase database schema — all 11 tables and pgvector extension
  - [x] 2.1 Write Supabase migration SQL file
    - Create `supabase/migrations/001_initial_schema.sql`
    - Enable `pgvector` extension first (`CREATE EXTENSION IF NOT EXISTS vector`)
    - Create all 11 tables in dependency order: `profiles`, `subjects`, `chapters`, `study_tasks`, `study_sessions`, `sleep_logs`, `mistakes`, `tests`, `reminders`, `playlists`, `documents`
    - Include all column definitions, constraints, foreign keys, and CHECK constraints exactly as specified in the design
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7_
  - [x] 2.2 Write CBSE Class 12 seed data SQL
    - Create `supabase/migrations/002_seed_data.sql`
    - Insert all five subjects: Physics, Chemistry, Mathematics, English, Computer Science
    - Insert all CBSE Class 12 chapters for each subject with their `board_weightage` values
    - _Requirements: 13.1, 13.2_

- [ ] 3. FastAPI backend core — `db.py`, `main.py`, CORS, global error handler
  - [x] 3.1 Implement `db.py` — Supabase client singleton with connection probe
    - Write `backend/app/db.py` with `get_client()` singleton and `verify_connection()` async probe
    - Probe queries `profiles` table with 10-second timeout; raises `RuntimeError` on failure
    - _Requirements: 2.4_
  - [-] 3.2 Implement `main.py` — FastAPI app with lifespan, CORS, and global exception handler
    - Write `backend/app/main.py` with `lifespan` context manager calling `verify_connection()`, `start_scheduler()`, and `stop_scheduler()`
    - Register CORS middleware using `settings.frontend_origin`
    - Register global `Exception` handler returning HTTP 500 JSON + logging full traceback
    - Expose `GET /health` returning `{"status": "ok"}`
    - Include router placeholders for `tasks`, `dashboard`, and `chat` with correct prefixes
    - _Requirements: 3.1, 3.4, 3.5, 3.6_
  - [ ]* 3.3 Write unit tests for `db.py` and `main.py` startup behaviour
    - Test that `verify_connection()` raises on timeout
    - Test that `/health` returns 200
    - Test that unhandled route exceptions return HTTP 500 JSON
    - _Requirements: 2.4, 3.4, 3.5_

- [x] 4. Priority Score engine
  - [x] 4.1 Implement `compute_priority_score` and `compute_deadline_pressure` in `priority.py`
    - Create `backend/app/priority.py`
    - Implement `clamp()`, `PriorityFactors` dataclass, `compute_priority_score()`, and `compute_deadline_pressure()`
    - Formula: `0.35·w + 0.25·d + 0.20·b + 0.10·bk + 0.10·r` with all inputs clamped to `[0.0, 1.0]`
    - _Requirements: 5.1, 5.4_
  - [ ]* 4.2 Write property test — Property 1: Priority Score Bounded Output
    - **Property 1: Priority Score Bounded Output**
    - Use `hypothesis` `@given` with five unclamped floats; assert result ∈ `[0.0, 1.0]`
    - **Validates: Requirements 5.1, 5.4**
  - [ ]* 4.3 Write property test — Property 2: Priority Score Formula Correctness
    - **Property 2: Priority Score Formula Correctness**
    - Use `hypothesis` with five floats pre-clamped to `[0.0, 1.0]`; assert result equals exact weighted sum
    - **Validates: Requirements 5.1**

- [~] 5. Checkpoint — Core infrastructure ready
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. REST API routes — tasks, chapters, sleep logs, mistakes, tests, reminders, sessions
  - [~] 6.1 Implement task service layer with priority score persistence
    - Create `backend/app/services/task_service.py`
    - Implement `create_task()` and `update_task()` that call `compute_priority_score()` and persist the result to `study_tasks.priority_score`
    - _Requirements: 5.2, 5.3_
  - [ ]* 6.2 Write property test — Property 3: Priority Score Persistence Round-Trip
    - **Property 3: Priority Score Persistence Round-Trip**
    - For any valid task creation payload, assert stored `priority_score` equals `compute_priority_score()` on the same inputs
    - **Validates: Requirements 5.2, 5.3**
  - [~] 6.3 Implement `routes/tasks.py` — task CRUD and session endpoints
    - Write `GET /tasks/today` returning today's tasks sorted by `priority_score` desc
    - Write `PATCH /tasks/{id}/status` updating status and broadcasting WS `task_update` event
    - Write `POST /tasks/{id}/session/start` creating a `study_sessions` record with status `active`
    - Write `POST /tasks/{id}/session/stop` closing the session, computing `duration_min`, and updating `actual_duration_min` on the task
    - Write `GET /sessions/today` returning all sessions for the current date
    - _Requirements: 4.1, 5.2, 5.3, 15.2, 15.3, 15.4, 15.5_
  - [ ]* 6.4 Write property test — Property 16: Study Session Actual Duration Accumulation
    - **Property 16: Study Session Actual Duration Accumulation**
    - For K completed sessions per task, assert `actual_duration_min` equals sum of all `duration_min` values
    - **Validates: Requirements 15.4**
  - [~] 6.5 Implement `routes/chapters.py` — chapter listing and completion
    - Write `GET /chapters?subject_id=` returning chapters with completion status and weakness score
    - Write `PATCH /chapters/{id}/complete` setting `is_completed=True` and `weakness_score=0.0`
    - _Requirements: 13.3, 13.4_
  - [ ]* 6.6 Write property test — Property 17: Chapter Completion Zeroes Weakness Score
    - **Property 17: Chapter Completion Zeroes Weakness Score**
    - Assert that after `PATCH /chapters/{id}/complete`, `weakness_score` is `0.0` and priority scores using that chapter reflect zero weakness
    - **Validates: Requirements 13.4**
  - [~] 6.7 Implement sleep log route — `POST /sleep-logs` with validation
    - Write `backend/app/routes/sleep_logs.py` with `POST /sleep-logs`
    - Implement `validate_sleep_log()` — reject when `sleep_end ≤ sleep_start` (with overnight crossing support), return HTTP 400 with descriptive message
    - Store `total_sleep_hours` computed from the interval
    - _Requirements: 10.2, 10.3_
  - [ ]* 6.8 Write property test — Property 7: Sleep Log Validation Rejects Invalid Intervals
    - **Property 7: Sleep Log Validation Rejects Invalid Intervals**
    - For any `(sleep_start, sleep_end)` where end is not strictly after start, assert HTTP 400 is returned
    - **Validates: Requirements 10.2**
  - [ ]* 6.9 Write property test — Property 8: Sleep Log Duration Computation
    - **Property 8: Sleep Log Duration Computation**
    - For any valid `(sleep_start, sleep_end)` pair, assert stored `total_sleep_hours` equals computed interval in hours
    - **Validates: Requirements 10.3**
  - [~] 6.10 Implement mistake routes — `POST /mistakes` with upsert and `GET /mistakes`
    - Write `backend/app/routes/mistakes.py`
    - `POST /mistakes`: implement `store_mistake()` upsert — increment `recurrence_count` on duplicate `(profile_id, subject_id, chapter_id, description)`
    - `GET /mistakes`: return mistakes grouped by `subject_id, chapter_id`, sorted by `recurrence_count` desc
    - _Requirements: 11.2, 11.3_
  - [ ]* 6.11 Write property test — Property 9: Mistake Recurrence Counting
    - **Property 9: Mistake Recurrence Counting**
    - For any tuple submitted N times, assert `recurrence_count` equals N
    - **Validates: Requirements 11.2**
  - [ ]* 6.12 Write property test — Property 10: Mistakes Endpoint Sort Order
    - **Property 10: Mistakes Endpoint Sort Order**
    - For any set of mistake records, assert the GET response is in non-increasing order of `recurrence_count`
    - **Validates: Requirements 11.3**
  - [~] 6.13 Implement test score routes — `POST /tests` with validation and `GET /tests/summary`
    - Write `backend/app/routes/tests.py`
    - `POST /tests`: implement `validate_test_score()` — reject `score < 0` or `score > max_score`, return HTTP 400
    - `GET /tests/summary`: return per-subject `AVG(percentage)` grouped by `subject_id`
    - _Requirements: 12.2, 12.3, 12.4_
  - [ ]* 6.14 Write property test — Property 11: Test Score Validation Rejects Out-of-Range Values
    - **Property 11: Test Score Validation Rejects Out-of-Range Values**
    - For any `(score, max_score)` where `score < 0` or `score > max_score`, assert HTTP 400
    - **Validates: Requirements 12.2**
  - [ ]* 6.15 Write property test — Property 12: Test Score Percentage Computation
    - **Property 12: Test Score Percentage Computation**
    - For any valid `(score, max_score)`, assert stored `percentage` equals `(score / max_score) × 100`
    - **Validates: Requirements 12.3**
  - [ ]* 6.16 Write property test — Property 13: Test Summary Average Correctness
    - **Property 13: Test Summary Average Correctness**
    - For any set of test records per subject, assert `/tests/summary` average equals arithmetic mean of individual percentages
    - **Validates: Requirements 12.4**
  - [~] 6.17 Implement reminder routes — `POST /reminders` and `GET /reminders`
    - Write `backend/app/routes/reminders.py`
    - `POST /reminders`: store reminder with `status='pending'`
    - `GET /reminders`: return today's reminders with status
    - _Requirements: 14.2, 14.5_
  - [ ]* 6.18 Write property test — Property 15: Reminder Status Is Monotone
    - **Property 15: Reminder Status Is Monotone**
    - Assert that once a reminder transitions to `fired`, no subsequent update sets it back to `pending`
    - **Validates: Requirements 14.4**

- [~] 7. Checkpoint — All REST routes complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. WebSocket manager
  - [~] 8.1 Implement `websocket_manager.py` — `ConnectionManager` with connect, broadcast, and disconnect
    - Write `backend/app/websocket_manager.py` with `ConnectionManager` class
    - `connect()`: accept connection, register, send `init` event with today's tasks, run keep-alive receive loop, remove on disconnect
    - `broadcast()`: send JSON event to all registered connections; silently remove dead connections
    - Export `ws_manager` singleton
    - Register `GET /ws` WebSocket endpoint in `main.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.5_
  - [ ]* 8.2 Write property test — Property 14: WebSocket Broadcast Completeness
    - **Property 14: WebSocket Broadcast Completeness**
    - For N connected mock WebSocket clients and any broadcast event, assert all N clients receive the event; assert clients that raise on send are removed without affecting remaining clients
    - **Validates: Requirements 7.3, 7.4, 7.5**

- [ ] 9. APScheduler background jobs and agents
  - [~] 9.1 Implement `sleep_agent.py` — `get_sleep_window()` with default fallback
    - Write `backend/app/agents/sleep_agent.py`
    - Query `sleep_logs` for today; fall back to `settings.default_sleep_start` / `settings.default_sleep_end` with a warning log when no record exists
    - Implement `validate_sleep_log()` helper for overnight crossing
    - _Requirements: 10.4, 10.5_
  - [~] 9.2 Implement AI provider stubs — `groq_provider.py` and `cerebras_provider.py`
    - Write `backend/app/providers/groq_provider.py` with `call_groq(messages) -> str` using `httpx.AsyncClient` against the Groq OpenAI-compatible API
    - Write `backend/app/providers/cerebras_provider.py` with `call_cerebras(messages) -> str` similarly
    - Both providers surface exceptions to the caller; timeout and retry policy handled by `tillu_brain.py`
    - _Requirements: 9.1, 9.2_
  - [~] 9.3 Implement `tillu_brain.py` — Groq → Cerebras → rule-based fallback
    - Write `backend/app/agents/tillu_brain.py`
    - `ask_tillu()`: try `call_groq()` with 15-second timeout; on failure try `call_cerebras()` with 15-second timeout; on failure call `_rule_based_plan()`
    - Implement `_rule_based_plan()` sorting context tasks by `priority_score` desc and returning a formatted string
    - _Requirements: 9.1, 9.2, 9.3, 9.7_
  - [ ]* 9.4 Write property test — Property 6: Rule-Based Fallback Always Produces a Plan
    - **Property 6: Rule-Based Fallback Always Produces a Plan**
    - For any non-empty list of task dicts, assert `_rule_based_plan()` returns a non-empty string containing at least one task entry
    - **Validates: Requirements 9.3**
  - [~] 9.5 Implement `planner_agent.py` — `run_nightly_plan()` with sleep window enforcement
    - Write `backend/app/agents/planner_agent.py`
    - `run_nightly_plan()`: gather context (sleep window, pending tasks, weakness data, test summary), call `ask_tillu()`, parse response, validate every scheduled block against the sleep window, discard or trim overlapping blocks, write to `study_tasks`, broadcast `daily_plan_created` WS event
    - `check_missed_tasks()`: mark overdue pending tasks as `missed`, broadcast `task_update` WS event per task
    - Enforce available-hours budget: total scheduled minutes ≤ 24×60 − sleep_duration_minutes
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_
  - [ ]* 9.6 Write property test — Property 4: Nightly Plan Respects Sleep Window
    - **Property 4: Nightly Plan Respects Sleep Window**
    - For any `(sleep_start, sleep_end)` and any task list, assert no scheduled block overlaps the sleep window after plan generation
    - **Validates: Requirements 9.5**
  - [ ]* 9.7 Write property test — Property 5: Nightly Plan Does Not Exceed Available Hours
    - **Property 5: Nightly Plan Does Not Exceed Available Hours**
    - For any sleep window, assert sum of scheduled task durations ≤ available waking minutes
    - **Validates: Requirements 9.6**
  - [~] 9.8 Implement `reminder_agent.py` — `check_reminders()` with three-channel dispatch
    - Write `backend/app/agents/reminder_agent.py`
    - `check_reminders()`: query reminders in the next 5-minute window with `status='pending'`; for each call `_dispatch_reminder()`
    - `_dispatch_reminder()`: call `_send_toast()` (plyer), `_play_chime()` (pygame), broadcast WS `reminder` event, update status to `fired`
    - Each channel failure is caught and logged independently; remaining channels still fire
    - _Requirements: 8.1, 8.2, 8.7, 14.3, 14.4_
  - [~] 9.9 Implement `scheduler.py` — `AsyncIOScheduler` with three jobs and safe error wrapper
    - Write `backend/app/scheduler.py`
    - Register nightly plan job (CronTrigger at `settings.scheduler_nightly_hour:settings.scheduler_nightly_minute`)
    - Register reminder check job (IntervalTrigger every 5 minutes)
    - Register missed task check job (IntervalTrigger every 30 minutes)
    - Wrap every job in `_safe_run()` to catch exceptions, log with traceback, and allow APScheduler to reschedule automatically
    - `start_scheduler()` / `stop_scheduler()` called from `main.py` lifespan
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [~] 10. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Next.js frontend shell — pages, components, WebSocket client, and state
  - [~] 11.1 Implement WebSocket client — `lib/socket.ts` with exponential back-off reconnect
    - Create `frontend/lib/socket.ts`
    - `createWebSocketClient(onMessage)` connects to `ws://localhost:8000/ws`; on close, schedules reconnect with delay starting at 1 s doubling to max 30 s; resets delay to 1 s on successful open; returns cleanup function
    - _Requirements: 7.6_
  - [~] 11.2 Implement `StudyContext` — React context, reducer, and `useWebSocket` hook
    - Create `frontend/lib/study-context.tsx`
    - State: `tasks`, `notifications`
    - Reducer handles: `task_update`, `reminder`, `daily_plan_created`, `task_rescheduled`, `init` WS events
    - `useWebSocket` hook wires `createWebSocketClient` into the context and dispatches events
    - _Requirements: 7.7_
  - [~] 11.3 Implement `TaskCard` component
    - Create `frontend/components/TaskCard.tsx`
    - Display: subject, chapter name, status badge (colour-coded for pending/in-progress/completed/missed), estimated duration, Priority Score bar, Start/Stop/Complete buttons
    - On Start: `POST /tasks/{id}/session/start` → dispatch `task_update` to context
    - On Stop: `POST /tasks/{id}/session/stop` → dispatch `task_update` to context
    - On Complete: `PATCH /tasks/{id}/status` → optimistic UI update
    - Show loading skeleton while data is pending
    - _Requirements: 4.1, 4.6, 4.7, 15.1, 15.2, 15.3_
  - [~] 11.4 Implement `NotificationBanner` component
    - Create `frontend/components/NotificationBanner.tsx`
    - Renders a dismissable banner when WS `reminder` or `missed` task events arrive
    - Banner visible until student clicks dismiss or navigates away
    - Missed task rows show distinct visual indicator (red border/badge)
    - _Requirements: 8.3, 8.5, 8.6_
  - [~] 11.5 Implement `SyllabusProgress` component
    - Create `frontend/components/SyllabusProgress.tsx`
    - Circular progress ring per subject showing completed/total chapters percentage
    - _Requirements: 4.3, 13.5_
  - [~] 11.6 Implement Home Dashboard page — `app/page.tsx`
    - Fetch today's tasks from `GET /tasks/today` on mount
    - Render `<TaskCard>` per task sorted by `priority_score` desc
    - Show loading skeleton during fetch
    - Integrate `<NotificationBanner>` for WS events
    - Include sleep log entry form (`POST /sleep-logs`)
    - Include mistake logging form (`POST /mistakes`)
    - Include test score entry form (`POST /tests`)
    - Include reminder creation form (`POST /reminders`)
    - _Requirements: 4.1, 4.6, 4.7, 10.1, 11.1, 12.1, 14.1_
  - [~] 11.7 Implement Timetable page — `app/timetable/page.tsx`
    - 7-column calendar grid showing current week
    - Study blocks as colour-coded tiles (one colour per subject)
    - Data from today's tasks plus adjacent days via `GET /tasks/today` (or a date-range endpoint)
    - _Requirements: 4.2_
  - [~] 11.8 Implement Syllabus page — `app/syllabus/page.tsx`
    - Accordion per subject listing chapters
    - Each chapter row: name, board weightage %, completion toggle (`PATCH /chapters/{id}/complete`), weakness indicator
    - Per-subject completion % from `GET /chapters?subject_id=X`
    - `<SyllabusProgress>` ring per subject
    - _Requirements: 4.3, 13.3, 13.4, 13.5_
  - [~] 11.9 Implement `TilluChat` component and chat route
    - Create `frontend/components/TilluChat.tsx` with chat input and scrollable message thread
    - Wire to `POST /chat` backend route
    - Write `backend/app/routes/chat.py` — accepts `{message, context}`, calls `ask_tillu()`, returns response text
    - _Requirements: 3.3_

- [~] 12. Checkpoint — Frontend pages and components complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Launcher script — `start.py`
  - [~] 13.1 Implement `start.py` launcher
    - Create `start.py` in the repo root
    - Spawn `uvicorn app.main:app --port {backend_port}` as subprocess in `backend/`
    - Spawn `npm run dev -- --port {frontend_port}` as subprocess in `frontend/`
    - Poll `GET /health` every 1 second until HTTP 200 or 30-second timeout; exit with error if timeout reached
    - On backend ready, print frontend URL; block until `Ctrl+C` (SIGINT)
    - On SIGINT: send SIGTERM to both child processes and wait for exit
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [~] 13.2 Create `run.bat` Windows wrapper
    - Write `run.bat` that executes `python start.py`
    - _Requirements: 1.1_

- [ ] 14. Remaining property-based tests — WebSocket, syllabus, and integration coverage
  - [ ]* 14.1 Write property test — Property 18: Syllabus Completion Percentage Accuracy
    - **Property 18: Syllabus Completion Percentage Accuracy**
    - For any subject with T total chapters and C completed, assert displayed percentage equals `round((C / T) * 100, 1)`
    - **Validates: Requirements 13.5**
  - [ ]* 14.2 Write integration tests for the full REST + WebSocket flow
    - Use `httpx.AsyncClient` with FastAPI's `TestClient` / `AsyncClient`
    - Cover: task creation → priority score persisted, sleep log rejection, mistake recurrence increment, test score rejection, reminder dispatch cycle
    - _Requirements: 5.2, 10.2, 11.2, 12.2, 14.3_

- [~] 15. Final checkpoint — full MVP wired and verified
  - Ensure all tests pass, ask the user if questions arise.

---

## Phase 2–6 Future Tasks (Optional)

- [ ]* F1. Phase 3 — Playwright/Chromium YouTube playlist integration
  - Implement `browser/chromium_controller.py` and `browser/youtube_player.py`
  - Gate behind `PLAYWRIGHT_ENABLED=true` env var; return HTTP 503 when disabled
  - _Requirements: 16.3, 16.4_
- [ ]* F2. Phase 4 — Sarvam STT/TTS voice interaction
  - Implement `providers/sarvam_voice.py` and `routes/voice.py`
  - Gate behind `SARVAM_ENABLED=true`; return HTTP 503 when disabled
  - _Requirements: 17.1, 17.2, 17.3, 17.4_
- [ ]* F3. Phase 6 — RAG document search with pgvector
  - Implement `agents/search_agent.py` and `providers/parallel_mcp.py`
  - Gate behind `RAG_ENABLED=true`; return HTTP 503 when disabled
  - _Requirements: 18.1, 18.2, 18.3, 18.4_
- [ ]* F4. Phase 2 — Full AI Planner context enrichment
  - Add weakness boost from top 10 mistake chapters to priority score computation in `planner_agent.py`
  - Pull `/tests/summary` averages into planner context
  - _Requirements: 11.4, 12.5_

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP delivery
- Property tests use `pytest` + `hypothesis`; run with `pytest backend/tests/`
- Each task references specific requirements for traceability
- Checkpoints at tasks 5, 7, 10, 12, and 15 ensure incremental validation
- All secrets must remain in `backend/.env` (gitignored) — never hard-coded in source
- Phase 2–6 features are gated by feature flags in `config.py`; stubs return HTTP 503 until enabled

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4", "2.1"] },
    { "id": 2, "tasks": ["2.2", "3.1", "4.1"] },
    { "id": 3, "tasks": ["3.2", "4.2", "4.3"] },
    { "id": 4, "tasks": ["3.3", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.5", "6.7", "6.10", "6.13", "6.17"] },
    { "id": 6, "tasks": ["6.4", "6.6", "6.8", "6.9", "6.11", "6.12", "6.14", "6.15", "6.16", "6.18"] },
    { "id": 7, "tasks": ["8.1", "9.1", "9.2"] },
    { "id": 8, "tasks": ["8.2", "9.3"] },
    { "id": 9, "tasks": ["9.4", "9.5", "9.8"] },
    { "id": 10, "tasks": ["9.6", "9.7", "9.9"] },
    { "id": 11, "tasks": ["11.1", "11.2"] },
    { "id": 12, "tasks": ["11.3", "11.4", "11.5"] },
    { "id": 13, "tasks": ["11.6", "11.7", "11.8", "11.9"] },
    { "id": 14, "tasks": ["13.1"] },
    { "id": 15, "tasks": ["13.2", "14.1", "14.2"] }
  ]
}
```
