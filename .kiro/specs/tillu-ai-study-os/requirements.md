# Requirements Document

## Introduction

Tillu AI Study OS is a local PC application for a Class 12 CBSE student studying Physics, Chemistry, Mathematics, English, and Computer Science. The system's mission is to help the student complete the full board exam syllabus by 30 November and achieve a score of 90% or above. It combines an AI study coach (Tillu), an intelligent daily planner, a real-time dashboard, a notification system, and a persistent cloud database to coordinate the student's study schedule from study task management through performance tracking.

The application runs entirely on a Windows PC. A single launcher script starts both the FastAPI backend and the Next.js frontend. All persistent data is stored in a cloud-hosted Supabase Postgres database. AI inference is handled by Groq as the primary provider and Cerebras as the fallback. Future phases will add Playwright-based browser automation, voice interaction, full analytics charts, and Retrieval-Augmented Generation (RAG) over uploaded documents.

---

## Glossary

- **Tillu**: The AI study coach persona embedded in the system. Tillu is strict but friendly, always plans using available time, weak chapters, deadlines, test scores, and sleep data, and never suggests distractions.
- **System**: The Tillu AI Study OS application as a whole, comprising the FastAPI backend and the Next.js frontend.
- **Backend**: The FastAPI Python process that exposes REST API routes, runs APScheduler jobs, manages WebSocket connections, and communicates with Supabase.
- **Frontend**: The Next.js / React dashboard that the student interacts with in a browser.
- **Launcher**: The single entry-point script (`start.py` or `run.bat`) that starts both the Backend and the Frontend.
- **Supabase**: The cloud-hosted Postgres database (supabase.io) used for all persistent storage, including pgvector embeddings and Realtime subscriptions.
- **APScheduler**: The Python scheduling library used inside the Backend to run nightly and periodic background jobs.
- **WebSocket Manager**: The Backend component that maintains live WebSocket connections to connected Frontend clients and broadcasts real-time events.
- **Priority Score**: A computed numeric score for each study task calculated as: `0.35 × weakness_score + 0.25 × deadline_pressure + 0.20 × board_weightage + 0.10 × backlog_score + 0.10 × revision_due_score`.
- **Nightly Plan**: The daily study schedule generated (or regenerated) each night by the AI Planner for the following day.
- **Toast Notification**: A Windows system notification (toast) displayed by the Backend's notification component.
- **Sound Alert**: An audio chime played on the local PC by the notification component.
- **Dashboard Visual Alert**: An in-app visual banner or badge rendered by the Frontend when a notification event is received via WebSocket.
- **Study Session**: A timed block of active study work recorded in the `study_sessions` table.
- **Mistake**: An error made by the student during practice or tests, recorded in the `mistakes` table for targeted review.
- **pgvector**: The Postgres vector extension enabled in Supabase, used in Phase 6 for RAG over the `documents` table.
- **Groq**: The primary AI inference provider used by Tillu for planning and Q&A.
- **Cerebras**: The fallback AI inference provider used when Groq is unavailable.
- **Playwright**: The browser automation library used in Phase 3+ for YouTube playlist integration.
- **Sarvam STT/TTS**: The speech-to-text and text-to-speech provider used in Phase 4+ for voice interaction.
- **Board Exam**: CBSE Class 12 board examination. Target score: 90%+. Syllabus completion deadline: 30 November.

---

## Requirements

### Requirement 1 — Single Launcher

**User Story:** As a student, I want to start the entire application with one command so that I do not have to manually start the backend and frontend separately.

#### Acceptance Criteria

1. THE Launcher SHALL start the Backend process and the Frontend process in the correct order with a single command (`python start.py` or `run.bat`).
2. WHEN the Backend process fails to start within 30 seconds, THE Launcher SHALL display an error message in the terminal and terminate both processes.
3. WHEN the Frontend process fails to start within 60 seconds after the Backend is ready, THE Launcher SHALL display an error message in the terminal and terminate both processes.
4. WHEN both processes are running, THE Launcher SHALL print the local URL of the Frontend dashboard to the terminal.
5. WHEN the student presses Ctrl+C in the Launcher terminal, THE Launcher SHALL gracefully terminate both the Backend process and the Frontend process.

---

### Requirement 2 — Supabase Database Schema

**User Story:** As a developer, I want all 11 required tables and the pgvector extension to be present in Supabase so that every part of the system has a persistent, structured data store.

#### Acceptance Criteria

1. THE System SHALL maintain the following tables in Supabase: `profiles`, `subjects`, `chapters`, `study_tasks`, `playlists`, `reminders`, `study_sessions`, `mistakes`, `tests`, `sleep_logs`, `documents`.
2. THE System SHALL have the `pgvector` extension enabled in the Supabase database before the `documents` table is created.
3. THE `documents` table SHALL include a vector embedding column compatible with the `pgvector` extension.
4. WHEN the Backend starts, THE Backend SHALL verify it can reach the Supabase database and SHALL log a startup error and exit if the connection cannot be established within 10 seconds.
5. THE `study_tasks` table SHALL store, at minimum: task ID, subject reference, chapter reference, scheduled date, estimated duration in minutes, actual duration in minutes, status (pending/in-progress/completed/missed), and the computed Priority Score.
6. THE `sleep_logs` table SHALL store, at minimum: log ID, profile reference, sleep start timestamp, sleep end timestamp, and total sleep duration in hours.
7. THE `mistakes` table SHALL store, at minimum: mistake ID, profile reference, subject reference, chapter reference, description text, recurrence count, and created timestamp.

---

### Requirement 3 — FastAPI Backend Scaffolding

**User Story:** As a developer, I want a structured FastAPI backend with clearly separated modules so that the codebase is maintainable and routes can be extended per phase.

#### Acceptance Criteria

1. THE Backend SHALL expose its REST API on a configurable port (default: 8000) defined in `config.py`.
2. THE Backend SHALL load all secrets (Supabase URL, Supabase anon key, Groq API key, Cerebras API key) from a `.env` file and SHALL NOT hard-code any secret values in source files.
3. THE Backend SHALL be structured with the following modules: `main.py`, `config.py`, `db.py`, `scheduler.py`, `websocket_manager.py`, and sub-packages `agents/`, `providers/`, `browser/`, `routes/`.
4. THE Backend SHALL expose a `/health` endpoint that returns HTTP 200 and a JSON body `{"status": "ok"}` when all dependencies are reachable.
5. WHEN an unhandled exception occurs in any route handler, THE Backend SHALL return an HTTP 500 response with a JSON error body and SHALL log the full traceback to the application log.
6. THE Backend SHALL implement CORS headers permitting requests from the Frontend's origin (configurable in `config.py`).

---

### Requirement 4 — Next.js Frontend Dashboard Shell

**User Story:** As a student, I want a web dashboard with Home, Timetable, and Syllabus pages so that I can see my daily plan and syllabus coverage at a glance.

#### Acceptance Criteria

1. THE Frontend SHALL provide a Home page that displays today's study tasks with their status (pending, in-progress, completed, missed) and Priority Score.
2. THE Frontend SHALL provide a Timetable page that displays the current week's scheduled study blocks in a calendar-style layout.
3. THE Frontend SHALL provide a Syllabus page that displays all five subjects (Physics, Chemistry, Mathematics, English, Computer Science) with per-chapter completion status.
4. THE Frontend SHALL use Next.js, React, Tailwind CSS, and shadcn/ui components exclusively for UI implementation.
5. THE Frontend SHALL be accessible via a browser on the same PC at `http://localhost:3000` (default port configurable).
6. WHEN the student marks a task as completed on the Home page, THE Frontend SHALL send an update request to the Backend and SHALL reflect the new status without a full page reload.
7. THE Frontend SHALL display a loading skeleton while data is being fetched from the Backend, rather than an empty or broken layout.

---

### Requirement 5 — Priority Score Computation

**User Story:** As a student, I want each study task to be ranked by importance so that I always work on the most critical chapters first.

#### Acceptance Criteria

1. THE Backend SHALL compute the Priority Score for each `study_task` using the formula: `priority_score = 0.35 × weakness_score + 0.25 × deadline_pressure + 0.20 × board_weightage + 0.10 × backlog_score + 0.10 × revision_due_score`.
2. THE Backend SHALL store the computed Priority Score in the `study_tasks` table whenever a task is created or updated.
3. WHEN any input factor (weakness_score, deadline_pressure, board_weightage, backlog_score, or revision_due_score) for a task is updated, THE Backend SHALL recompute and persist the Priority Score for that task.
4. THE Backend SHALL normalise each input factor to the range [0.0, 1.0] before applying the formula.
5. THE Frontend SHALL display study tasks on the Home page sorted in descending order of Priority Score.

---

### Requirement 6 — APScheduler Background Jobs

**User Story:** As a student, I want the system to automatically generate my daily plan, check for reminders, and flag missed tasks without me having to trigger these actions manually.

#### Acceptance Criteria

1. THE Scheduler SHALL run a nightly plan job each night at a configurable time (default: 22:00 local time) that generates the next day's study schedule and writes it to the `study_tasks` table.
2. THE Scheduler SHALL run a reminder check job every 5 minutes that queries the `reminders` table and triggers notifications for reminders whose scheduled time falls within the next 5 minutes.
3. THE Scheduler SHALL run a missed task check job every 30 minutes that identifies `study_tasks` with status `pending` whose scheduled end time has passed and updates their status to `missed`.
4. WHEN a scheduled job raises an unhandled exception, THE Scheduler SHALL log the error with full context and SHALL reschedule the job for its next regular interval without crashing the Backend.
5. THE Scheduler SHALL use APScheduler with the `AsyncIOScheduler` variant so that jobs execute on the same event loop as the FastAPI Backend.

---

### Requirement 7 — WebSocket Live Updates

**User Story:** As a student, I want the dashboard to update in real time when tasks are completed, reminders fire, or the plan changes so that I always see current information without refreshing the page.

#### Acceptance Criteria

1. THE Backend SHALL maintain a WebSocket endpoint at `/ws` that accepts connections from Frontend clients.
2. WHEN a Frontend client connects to `/ws`, THE WebSocket Manager SHALL register the connection and SHALL send the client the current day's task list as the initial payload.
3. WHEN a study task status changes (completed, missed, or rescheduled), THE WebSocket Manager SHALL broadcast a JSON event to all connected Frontend clients within 2 seconds of the change.
4. WHEN a reminder fires, THE WebSocket Manager SHALL broadcast a reminder event to all connected Frontend clients within 2 seconds of the trigger.
5. WHEN a Frontend client disconnects from `/ws`, THE WebSocket Manager SHALL remove the connection from its registry without affecting other connected clients.
6. THE Frontend SHALL establish a WebSocket connection to the Backend on page load and SHALL automatically attempt reconnection with exponential back-off (starting at 1 second, maximum 30 seconds) if the connection drops.
7. WHEN a WebSocket event is received by the Frontend, THE Frontend SHALL update the relevant UI component (task list, notification banner) without a full page reload.

---

### Requirement 8 — Notification System

**User Story:** As a student, I want to be alerted for reminders and missed tasks through Windows toast notifications, a sound chime, and a dashboard banner so that I never miss a scheduled study block.

#### Acceptance Criteria

1. WHEN a reminder event is triggered, THE Backend SHALL display a Windows toast notification on the local PC containing the reminder title and scheduled time.
2. WHEN a reminder event is triggered, THE Backend SHALL play an audio chime on the local PC's default audio output.
3. WHEN a reminder event is received by the Frontend via WebSocket, THE Frontend SHALL display a Dashboard Visual Alert (banner or badge) in the dashboard header area containing the reminder title.
4. WHEN a task status is set to `missed`, THE Backend SHALL display a Windows toast notification indicating the missed task name and subject.
5. WHEN a task status is set to `missed`, THE Frontend SHALL display a Dashboard Visual Alert highlighting the missed task in the task list with a distinct visual indicator (e.g., red border or badge).
6. THE Dashboard Visual Alert SHALL remain visible until the student dismisses it or navigates away from the current page.
7. IF the audio output device is unavailable, THEN THE Backend SHALL log the audio failure and SHALL still deliver the Windows toast notification and trigger the WebSocket event.

---

### Requirement 9 — AI Planner (Phase 2)

**User Story:** As a student, I want Tillu to intelligently plan my daily study schedule using my weakness data, deadlines, board weightage, and sleep history so that I make the fastest possible progress toward 90%+.

#### Acceptance Criteria

1. WHEN the nightly plan job runs, THE AI Planner SHALL call the Groq inference provider with the Tillu system prompt to generate the next day's study schedule.
2. IF the Groq provider returns an error or times out after 15 seconds, THEN THE AI Planner SHALL retry the request using the Cerebras provider.
3. IF both Groq and Cerebras fail, THEN THE AI Planner SHALL fall back to a rule-based schedule that prioritises tasks by descending Priority Score and SHALL log the fallback event.
4. THE AI Planner SHALL include the student's available study time, current chapter weakness scores, proximity to the 30 November deadline, board exam weightage per chapter, backlog tasks, and pending revision tasks in the prompt context.
5. THE AI Planner SHALL not schedule study tasks during the student's recorded sleep window from the `sleep_logs` table.
6. THE AI Planner SHALL limit total scheduled study time per day to the available hours calculated from the student's sleep log and any recorded commitments.
7. THE Tillu system prompt used by THE AI Planner SHALL instruct Tillu to protect the student's sleep schedule and to never suggest distracting activities.

---

### Requirement 10 — Sleep Log Tracking

**User Story:** As a student, I want to log my sleep times so that Tillu can protect my sleep schedule and plan study blocks only during waking hours.

#### Acceptance Criteria

1. THE Frontend SHALL provide a sleep log entry form on the dashboard where the student can record sleep start time, sleep end time, and date.
2. WHEN a sleep log entry is submitted, THE Backend SHALL validate that sleep end time is after sleep start time and SHALL return an HTTP 400 error with a descriptive message if the validation fails.
3. THE Backend SHALL store each valid sleep log entry in the `sleep_logs` table with the computed total sleep duration in hours.
4. THE AI Planner SHALL read the most recent sleep log entry before generating the nightly plan and SHALL use the recorded sleep window to exclude unavailable hours from the plan.
5. WHEN no sleep log entry exists for the current day, THE AI Planner SHALL use a default sleep window of 23:00–06:00 and SHALL log a warning indicating that the default was applied.

---

### Requirement 11 — Mistake Tracking

**User Story:** As a student, I want to log mistakes I make during practice so that Tillu can prioritise revision of those chapters in future plans.

#### Acceptance Criteria

1. THE Frontend SHALL provide a mistake logging form where the student can record the subject, chapter, and a description of the mistake.
2. WHEN a mistake is submitted, THE Backend SHALL store it in the `mistakes` table and SHALL increment the `recurrence_count` if an identical subject-chapter-description combination already exists.
3. THE Backend SHALL expose a `/mistakes` GET endpoint that returns mistakes grouped by subject and chapter, sorted by descending recurrence count.
4. THE AI Planner SHALL fetch the top 10 chapters by total mistake recurrence count and SHALL increase the `weakness_score` for those chapters proportionally when computing Priority Scores for the next day's plan.

---

### Requirement 12 — Test Score Recording

**User Story:** As a student, I want to record test scores so that Tillu can track my performance per subject and adjust planning to reinforce weak areas.

#### Acceptance Criteria

1. THE Frontend SHALL provide a test score entry form where the student can enter the subject, chapter or topic, score obtained, and maximum score.
2. WHEN a test score is submitted, THE Backend SHALL validate that the score obtained is greater than or equal to zero and less than or equal to the maximum score, and SHALL return an HTTP 400 error if the validation fails.
3. THE Backend SHALL store each valid test score in the `tests` table with a computed percentage score.
4. THE Backend SHALL expose a `/tests/summary` GET endpoint that returns per-subject average percentage scores calculated from all recorded test entries.
5. THE AI Planner SHALL retrieve the per-subject average scores from `/tests/summary` and SHALL use a lower average score as an input to the `weakness_score` factor when computing Priority Scores.

---

### Requirement 13 — Syllabus Chapter Management

**User Story:** As a student, I want the system to know all chapters per subject so that planning and progress tracking can be tied to specific syllabus units.

#### Acceptance Criteria

1. THE System SHALL seed the `subjects` table with the five CBSE Class 12 subjects: Physics, Chemistry, Mathematics, English, and Computer Science.
2. THE System SHALL seed the `chapters` table with all CBSE Class 12 board exam chapters for each subject, including the board weightage percentage for each chapter.
3. THE Backend SHALL expose a `/chapters` GET endpoint that returns all chapters for a given subject, including completion status and current weakness score.
4. WHEN the student marks a chapter as completed via the Syllabus page, THE Backend SHALL update the chapter's completion status in the `chapters` table and SHALL set the chapter's `weakness_score` contribution to zero in subsequent Priority Score calculations.
5. THE Frontend Syllabus page SHALL display overall completion percentage per subject calculated as the ratio of completed chapters to total chapters.

---

### Requirement 14 — Reminder Management

**User Story:** As a student, I want to create and manage study reminders so that I am prompted at the right time to start a scheduled study block.

#### Acceptance Criteria

1. THE Frontend SHALL provide a reminder creation form where the student can set a reminder title, target date, and time.
2. WHEN a reminder is created, THE Backend SHALL store it in the `reminders` table with status `pending`.
3. WHEN the reminder check job finds a reminder scheduled within the next 5 minutes with status `pending`, THE Backend SHALL trigger all three notification channels (Windows toast, audio chime, WebSocket Dashboard Visual Alert).
4. WHEN a reminder notification has been dispatched, THE Backend SHALL update the reminder's status to `fired` in the `reminders` table.
5. THE Backend SHALL expose a `/reminders` GET endpoint that returns all reminders for the current day, including their status.

---

### Requirement 15 — Study Session Tracking

**User Story:** As a student, I want to track the time I actually spend studying so that the system has accurate data to improve future plans.

#### Acceptance Criteria

1. THE Frontend SHALL provide Start and Stop controls on each task card on the Home page so the student can record an active study session.
2. WHEN the student clicks Start on a task, THE Frontend SHALL send a session start event to the Backend and THE Backend SHALL create a `study_sessions` record with the start timestamp and status `active`.
3. WHEN the student clicks Stop on a task, THE Frontend SHALL send a session stop event to the Backend and THE Backend SHALL update the corresponding `study_sessions` record with the end timestamp, compute the actual duration in minutes, and set status to `completed`.
4. THE Backend SHALL update the `actual_duration` field of the associated `study_task` with the sum of all completed session durations for that task.
5. THE Backend SHALL expose a `/sessions/today` GET endpoint that returns all study sessions for the current calendar day, including start time, end time, and duration.

---

### Requirement 16 — Playlist Integration (Phase 3)

**User Story:** As a student, I want the system to manage YouTube study playlists per subject so that I can access curated video resources directly from the dashboard.

#### Acceptance Criteria

1. THE Backend SHALL store playlist entries in the `playlists` table with at minimum: playlist ID, subject reference, playlist URL, title, and watch status.
2. THE Frontend SHALL display associated playlists on the Syllabus page alongside each subject.
3. WHERE Playwright is enabled, THE System SHALL use Playwright with a Chromium browser to open YouTube playlists on the student's PC when the student clicks a playlist link.
4. WHERE Playwright is enabled, THE System SHALL mark a playlist's watch status as `watched` in the `playlists` table when the student confirms completion via the dashboard.

---

### Requirement 17 — Voice Interaction (Phase 4)

**User Story:** As a student, I want to speak to Tillu and hear responses so that I can interact with my study coach hands-free.

#### Acceptance Criteria

1. WHERE Sarvam STT/TTS is enabled, THE Frontend SHALL display a microphone button that the student can press to begin a voice query.
2. WHERE Sarvam STT/TTS is enabled, WHEN the student activates the microphone, THE Frontend SHALL stream audio to the Backend which SHALL forward it to the Sarvam STT provider and receive a text transcript.
3. WHERE Sarvam STT/TTS is enabled, WHEN the text transcript is ready, THE Backend SHALL forward it to Tillu (via Groq or Cerebras) and SHALL convert the text response to audio using the Sarvam TTS provider.
4. WHERE Sarvam STT/TTS is enabled, THE Frontend SHALL play the TTS audio response through the student's default audio output.

---

### Requirement 18 — RAG Document Search (Phase 6)

**User Story:** As a student, I want to upload study documents and query them through Tillu so that I can get chapter-specific answers grounded in my own notes and textbooks.

#### Acceptance Criteria

1. WHERE RAG is enabled, THE Backend SHALL accept document uploads (PDF or plain text) and SHALL chunk, embed, and store the vectors in the `documents` table using pgvector.
2. WHERE RAG is enabled, WHEN Tillu receives a query that requires factual retrieval, THE Backend SHALL perform a vector similarity search on the `documents` table and SHALL include the top 5 matching chunks in the Groq/Cerebras prompt context.
3. WHERE RAG is enabled, THE Frontend SHALL provide a document upload interface on the dashboard where the student can upload files and associate them with a subject.
4. WHERE Parallel Search MCP is enabled, THE Backend SHALL use the Parallel Search MCP tool to retrieve web search results in addition to document chunks when composing the RAG context.
