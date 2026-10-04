# TILLU — built by and for Heoster

TILLU is Heoster’s private, single-owner personal AI assistant and agent harness. It combines natural-language Chat, registered tool calling, approval-gated actions, executable plans, layered private memory, live research, a controlled Playwright browser, files and RAG, notes, canvas, tasks, calendar, automations, optional communications, and Class 12 study support.

> **Current status: functional private local MVP — not yet a durable hosted-production release.** Production Supabase repositories exist and fail closed, but migrations, RLS, Storage, queues, and repository behavior have not been verified against Heoster’s real Supabase project. See [What TILLU is](docs/WHAT_TILLU_IS.md) and [MVP readiness](docs/MVP_READINESS.md).

## What makes TILLU an agent harness

TILLU does more than generate text:

- Selects registered read tools automatically.
- Compiles typed, bounded plans from registered capabilities.
- Evaluates evidence and replans no more than twice.
- Displays exact consequential actions before execution.
- Requires explicit approval for writes and external effects.
- Atomically claims proposals and plans to prevent duplicate execution.
- Persists conversations, rich response metadata, plans, results, memory, and workspace data.
- Streams orchestration phases to the unified TILLU Brain UI over SSE.
- Uses deterministic fallbacks when no model provider is available.

TILLU never executes arbitrary shell commands, arbitrary generated Python, or unregistered functions.

## Governed brain cycle

A normal Assistant request follows:

1. **Intent detection** — model-assisted with deterministic fallback.
2. **Planning** — selects the smallest safe set of registered read capabilities.
3. **Tool execution** — server-owned functions run with validated arguments.
4. **Context assembly** — tool evidence, recent history, preferences, and approved memory.
5. **Evidence evaluation** — checks missing, failed, stale, or insufficient results.
6. **Bounded revision** — retries registered reads at most twice.
7. **Response generation** — adaptive provider routing or deterministic fallback.
8. **Verification** — removes unsupported citation references.

Executable plans may contain up to eight ordered registered read/action capabilities. The complete plan is persisted and shown for approval before any action runs.

## Natural Chat — no command grammar required

Core MVP actions work without special commands or a configured model. Heoster can ask naturally:

- “Remind me to revise electrostatics.”
- “Remember my friend Aman’s email is aman@example.com.”
- “Make a canvas for ray diagrams.”
- “Schedule Physics revision tomorrow at 6 pm.”
- “Complete the task Revise optics.”
- “Create a daily weather brief called Morning Update at 7 am.”
- “Draft an email to teacher@example.com with subject Project saying I completed it.”

Ambiguous resource names fail closed rather than being guessed. Configured models broaden natural-language interpretation and multi-capability planning. Consequential changes still require approval.

## Current capabilities

### Unified Assistant

- Chat, controlled Browser, Notes, and persistent Canvas in one workspace
- Structured Markdown-like answers, widgets, citations, tool chips, provider/model identity, and generation metadata
- Live TILLU Brain phases over SSE with cancellation
- Conversation history, search, rename, pin, archive, deletion, and rich-message reconstruction

### Tools and actions

- Approximately 20 read capabilities covering web, webpages, weather, news, trends, documents, files, research, tasks, calendar, notes, canvas, automations, syllabus, browser history, activity, settings, memory, Gmail, calculator, and system context
- Approximately 29 approval-gated action capabilities covering workspace CRUD, progress, files, browser control, automations, settings, Gmail drafts, WhatsApp, and memory
- One typed capability registry is the canonical source for tool discovery, risk, schema, and approval policy

### Controlled browser

- Real server-side Playwright Chromium
- Isolated owner sessions
- Navigation, page text, screenshots, click, type, key press, and close
- Manual UI control and Chat-generated proposals
- Public-network URL validation and request interception

Browser sessions are currently process-local and are lost on backend restart.

### Private layered memory

Owner-controlled layers:

- Identity
- People and sensitive contact details
- Preferences
- Projects
- Routines
- Episodic experiences

Explicit “remember…” requests create approval proposals. The Memory page supports review and deletion. Proactive routine suggestions and in-app activity tracking are opt-in; TILLU does not covertly monitor GPS, microphones, other apps, or external device activity.

### Models

The in-app library can discover hundreds of models and mark free/free-tier entries. The active free/free-tier Chat routing pool includes models from:

- Groq
- Cerebras
- Google Gemini, including Gemini 2.5 Flash
- Cloudflare Workers AI
- OpenRouter’s free router

Routing considers phase, capability, cost, latency, quota pressure, provider health, 429 cooldown, and circuit-breaker state. Catalog presence does not mean a model is callable: private provider keys are still required.

### Knowledge and files

- Bounded PDF upload and structural inspection
- Content-addressed storage
- Page-aware extraction and chunking
- Lexical retrieval with citations
- Optional Supabase Storage

OCR, tables/formulas, hybrid embeddings, pgvector reranking, and durable ingestion workers remain incomplete.

## Repository layout

```text
apps/
  api/        FastAPI, LangGraph, capabilities, repositories, browser, RAG, worker
  web/        React/Vite PWA and unified Assistant workspace
  mobile/     Expo Android foundation
  desktop/    Tauri desktop foundation
supabase/
  migrations/ Postgres, RLS, Storage, queue, memory, and plan schema
render.yaml   Render deployment blueprint
deploy/       Hosting control documentation; canonical source remains under apps/
docs/         Architecture, readiness, memory, models, deployment, and audits
```

## Local quick start

### API

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
# On Linux, install browser libraries if required:
# python -m playwright install-deps chromium
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Web

```bash
cd apps/web
npm install
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173`.

Development mode uses an explicit local Heoster identity and SQLite. Optional external integrations remain disabled until configured.

## Configuration

Copy the examples instead of committing secrets:

```bash
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
```

Production requires at minimum:

- `ENVIRONMENT=production`
- `OWNER_USER_ID=<Heoster auth.users UUID>`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- Restricted `CORS_ORIGINS`
- At least one configured AI provider

Gmail, WhatsApp, browser communications, and additional search providers are optional and must fail closed when unconfigured.

## Supabase production setup

Apply migrations in order through:

```text
supabase/migrations/010_proactive_briefings.sql
```

Do not claim production readiness until live tests verify:

- Owner and non-owner RLS behavior
- Service-role repository ownership filters
- Storage upload/download/delete
- Durable queue claims, leases, retries, and idempotency
- Atomic action-proposal and executable-plan claims
- Memory ownership and deletion
- Backup and restore behavior

## Tests and builds

Latest verified local baseline:

- **24 backend tests passed**
- Frontend production build passed with **1,933 transformed modules**
- Runtime-tested natural actions, approval claims, general plan execution, browser navigation/screenshots, SSE, canvas persistence, memory, and model-library discovery

Run checks:

```bash
cd apps/api
PYTHONPATH=. pytest tests -q

cd ../web
npm run build
```

## Important unfinished work

1. Live Supabase, RLS, Storage, and queue verification with Heoster’s credentials.
2. Replace the remaining demo-style PYQ collection connector with a real trusted-source download/index worker.
3. Provider token streaming, SSE reconnect, and durable run continuation.
4. Durable browser session leasing and remote worker/session-affinity support.
5. OCR, hybrid pgvector retrieval, reranking, and isolated ingestion workers.
6. Push/native notifications and a durable proactive scheduler.
7. Gmail OAuth lifecycle and WhatsApp webhooks/receipts/templates.
8. Mobile and desktop feature parity, signing, updates, and secure token storage.
9. Split the large backend and frontend modules into feature-owned packages.
10. Broader RLS, security, repository-contract, provider, browser, queue, and end-to-end tests.

## Safety and privacy

- TILLU is private and owner-only.
- Models cannot register or directly execute tools.
- Writes and external effects require approval.
- Action proposals and plans are persisted and atomically claimed.
- Browser and web retrieval apply public-network restrictions.
- Memory is visible, deletable, layered, and owner-scoped.
- Provider and Supabase secrets stay on the backend.
- Optional integrations are not reported as connected without credentials.

Do not store irreplaceable data in hosted production until live Postgres persistence, RLS, backups, and restore procedures have been verified.

## Documentation

- [What TILLU is](docs/WHAT_TILLU_IS.md)
- [MVP readiness](docs/MVP_READINESS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Architecture review](docs/ARCHITECTURE_REVIEW_2026-10-01.md)
- [Memory system](docs/MEMORY_SYSTEM.md)
- [Proactive briefings and autonomous execution](docs/PROACTIVE_AUTONOMY.md)
- [Model library](docs/MODEL_LIBRARY.md)
- [Foundation remediation status](docs/FOUNDATION_REMEDIATION_STATUS.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Security audit](docs/ARCHITECTURE_AUDIT.md)
