# TILLU Architecture Review

**Date:** 1 October 2026  
**Product:** TILLU — private personal assistant built by and for Heoster  
**Review basis:** Current repository, implemented runtime paths, migrations, tests, and verified local workflows.

## Executive verdict

TILLU has a credible agent-system architecture and is substantially more than a chatbot. It combines a bounded LangGraph reasoning cycle, server-owned tools, approval-gated mutations, private workspace data, controlled Playwright browsing, provider routing, RAG, automations, and a unified Assistant UI.

It is a **strong local/private MVP**, but it is **not yet a production-grade always-on Jarvis system**. The largest difference is operational maturity: live Supabase verification, durable execution, streaming, browser durability, comprehensive tests, observability, and complete metadata persistence are unfinished.

| Area | Rating | Verdict |
|---|---:|---|
| Product architecture | 8/10 | Correct broad direction for a private Jarvis-style assistant |
| Agent/tool design | 7.5/10 | Strong read loop and safety boundary; action system needs unification |
| Local MVP quality | 8/10 | Functional and runtime-tested across important workflows |
| Security design | 7/10 | Good owner/approval/SSRF foundations; production verification is incomplete |
| Data architecture | 6.5/10 | Production repository exists, but live Supabase/RLS behavior is unverified |
| Reliability/operations | 5/10 | Process-local browser state, limited tests, no tracing or durable run continuation |
| Frontend architecture | 6/10 | Capable unified UX, but concentrated in one very large component file |
| Hosted-production readiness | 5/10 | Deployable foundation, not yet honestly production complete |

## 1. Implemented system shape

```text
Web PWA (React/Vite)
Mobile shell (Expo)       ── HTTPS/Auth ──> FastAPI API
Desktop shell (Tauri)                         │
                                             ├─ Owner authentication
                                             ├─ Unified chat/action API
                                             ├─ LangGraph orchestration
                                             │   Intent → plan → read tools
                                             │   → evidence check → ≤2 revisions
                                             │   → response → citation verification
                                             ├─ Approval proposal engine
                                             ├─ Provider/model gateway
                                             ├─ Playwright browser runtime
                                             ├─ PDF/RAG pipeline
                                             ├─ Integration adapters
                                             └─ Persistence boundary
                                                 ├─ SQLite: development/test
                                                 └─ Supabase: production
                                                     Postgres/Auth/Storage/queue
```

### Core source boundaries

- `apps/web/src/main.jsx`: unified product UI, including Assistant, Browser, Notes, Canvas, tasks, calendar, research, settings, and operations.
- `apps/api/app/main.py`: HTTP API, action proposals, resource operations, controlled-browser endpoints, and integration endpoints.
- `apps/api/app/orchestrator.py`: authoritative bounded read/reason/respond graph and read-tool registry.
- `apps/api/app/repository.py`: environment-based persistence boundary.
- `apps/api/app/database.py`: SQLite development/test implementation.
- `apps/api/app/supabase_repository.py`: production Postgres implementation.
- `apps/api/app/browser_control.py`: isolated server-side Playwright sessions.
- `apps/api/app/providers.py`: adaptive multi-provider model routing.
- `apps/api/app/rag.py`, `fileguard.py`, `downloads.py`: document safety and retrieval.
- `supabase/migrations/001–007`: schema, RLS, storage, queue hardening, and repository support.

## 2. What is architecturally strong

### A. Server authority is correctly placed

Models do not directly mutate state. The server owns tool registration, validates selected tool names, performs calls, and returns typed results. This is the correct trust boundary for an agent with personal data and external integrations.

### B. Consequential actions require approval

Chat creates persisted, expiring action proposals. Approved actions are atomically claimed before execution, preventing the earlier duplicate-execution race. This is one of the strongest parts of the architecture.

### C. The reasoning loop is bounded

The graph has explicit intent, planning, execution, context assembly, evidence evaluation, a maximum of two revision passes, response generation, and citation cleanup. Bounded correction is safer and easier to operate than an unconstrained autonomous loop.

### D. Deterministic fallbacks are first-class

Current-time, calculator, command routing, tool selection heuristics, approval parsing, and structured fallback responses continue to work when model providers are unavailable. This matters because many configured providers are free-tier or quota-limited.

### E. Private-owner design is explicit

Production authentication checks Heoster's configured owner identity. Owner filters are applied in the service-role repository as defense in depth, even though service-role access bypasses RLS.

### F. The controlled browser is real

The browser uses server-side Chromium through Playwright, not a fake iframe. It supports isolated contexts, navigation, page state, screenshots, close controls, and approval-gated click/type/key actions. Runtime navigation and screenshot creation have been verified.

### G. Production persistence now has a fail-closed boundary

Production imports the Supabase repository; development/test imports SQLite. Production startup requires Supabase configuration and probes required schema. There is no intended production fallback to SQLite.

### H. Deployment topology is sensible

Vercel for the web app, Render Docker for FastAPI/Playwright, a separate worker, and Supabase for Auth/Postgres/Storage are reasonable low-cost choices for this product stage.

## 3. Major architectural weaknesses

### Critical: production data behavior is not live-verified

The Supabase repository is implemented, but migrations, RLS, Storage, RPCs, queue leasing, and all CRUD paths have not been exercised against Heoster's real project. Service-role requests can hide RLS mistakes. Production readiness cannot be claimed until both authenticated client RLS tests and backend service-role repository tests pass live.

### Critical: browser sessions are process-local

Browser contexts live in `BrowserRuntime.sessions`. They disappear on restart and cannot be moved between workers. The Docker command correctly limits the API to one worker, but that also prevents horizontal scaling. Durable session metadata alone is insufficient; a session-affinity or remote-browser architecture is required.

### High: read tools and action tools use two different systems

Read tools are `ToolSpec` entries inside the orchestrator. Mutations use `ACTION_SCHEMAS`, deterministic regexes, model-assisted routing, labels, and a large decision dispatch in `main.py`. These definitions can drift. A single typed capability registry should describe:

- input schema;
- risk and approval policy;
- read/write/external classification;
- execution handler;
- UI preview formatter;
- audit redaction policy;
- idempotency behavior;
- availability/configuration state.

The current system exposes many actions, but it does not yet guarantee that every new API function automatically becomes a safe Chat capability.

### High: `main.py` is becoming an application monolith

Routes, proposal parsing, action inference, execution, browser operations, settings, files, research, calendar, notes, and automations are concentrated in one module. This increases regression risk and makes security review difficult.

Recommended split:

```text
api/routes/chat.py
api/routes/browser.py
api/routes/files.py
api/routes/workspace.py
api/routes/integrations.py
services/actions.py
services/capabilities.py
services/approvals.py
repositories/interfaces.py
```

### High: the frontend is also monolithic

Most UI logic is in one very large `main.jsx`. It works, but component ownership, testing, code splitting, accessibility, and state consistency will degrade as features expand. Browser, Chat, Notes, Canvas, Settings, and each workspace page should be separate feature modules.

### High: chat results are not fully durable

Conversation messages persist text, but full response metadata—citations, widgets, tool results, agent-cycle phases, provider/model identity, usage, proposal references, and errors—is not consistently persisted. Reloading a conversation therefore cannot reconstruct the original rich response exactly.

### High: no streaming or durable run continuation

Chat waits for a whole response. There is no SSE token/tool-event stream, cancellation, reconnect, or durable continuation after API restart. Long research or browser operations will feel fragile.

### High: test coverage is too small

Seven tests are insufficient for the current security and capability surface. Missing coverage includes:

- owner rejection and token expiry;
- live RLS policies;
- action-schema and handler parity;
- duplicate/concurrent approvals;
- SSRF redirects and DNS rebinding defenses;
- browser ownership and artifact access;
- upload quarantine and parser limits;
- queue leases, retries, and idempotency;
- every SQLite/Supabase repository contract;
- provider fallback and quota behavior;
- end-to-end unified Chat workflows.

## 4. Agent and tool-calling review

### Current read flow

The model may select only registered read tools. Calls are capped, validated, quota-checked, executed by the server, assembled into bounded context, and evaluated for sufficiency. This is sound.

### Current action flow

Actions are recognized by deterministic commands or a schema-bounded model router. They produce review widgets and execute only after approval. This is safe in principle.

### Remaining problems

1. Action inference runs outside the LangGraph planning cycle.
2. Resource IDs often need to be visible in a prior resource card or explicit command.
3. Deterministic syntax is useful but brittle.
4. There is no general semantic entity resolver with confidence scoring.
5. Some operations are API capabilities but not natural Chat capabilities.
6. Tool output schemas are dictionaries rather than strongly versioned result models.
7. Read operations are sequential; independent calls could execute concurrently.
8. Tool timeouts, per-tool budgets, and cancellation are inconsistent.

### Recommended target

Create one `CapabilitySpec` registry and let the graph produce either:

- `ReadCall` → execute immediately;
- `ProposedAction` → persist and display approval;
- `UnavailableCapability` → explain missing credentials or infrastructure.

The model should never emit arbitrary endpoint names. It should select versioned capability IDs validated against generated Pydantic/JSON schemas.

## 5. Data and persistence review

### Good

- Environment-based repository selection is explicit.
- Production is fail-closed.
- Owner predicates are applied in backend queries.
- Supabase migrations include RLS and queue RPCs.
- UUIDs are portable between stores.
- Cloud PDF objects are content-addressed.

### Problems

- SQLite and Supabase implementations are handwritten separately, so behavior can diverge.
- There is no repository contract test suite run against both implementations.
- Some ordering and filtering semantics differ between stores.
- Service-role use means backend tests do not prove RLS correctness.
- `JOBS` and `PROGRESS` still exist as process caches; production data reads should never depend on them.
- Message content/schema evolution is not versioned.
- No formal backup/restore drill or retention policy is documented.

### Recommendation

Define repository protocols and a shared contract-test suite. Run the same tests against temporary SQLite and a Supabase/Postgres test project. Treat Postgres as authoritative and caches as explicitly disposable.

## 6. Security review

### Existing safeguards

- owner-only authentication;
- backend-only service-role key;
- approval gates;
- atomic proposal claims;
- audit events;
- rate/body/security middleware;
- PDF size/signature/structure bounds;
- public-network URL policy;
- browser request interception;
- isolated browser contexts;
- optional integrations disabled when unconfigured;
- no credential values hard-coded in source.

### Remaining security risks

1. DNS rebinding is not fully prevented because validation is not tied to a pinned resolved address/egress proxy.
2. Browser automation can still expose authenticated page content to model context unless explicit data-release policy is added.
3. CSS-selector actions are powerful and require stronger domain/action previews.
4. PDF structural quarantine is not malware certification or OS-level parser isolation.
5. Audit redaction rules are not centrally typed.
6. Gmail and WhatsApp webhook verification paths are incomplete.
7. Live RLS behavior is unverified.
8. Browser artifacts need lifecycle cleanup and retention limits.
9. There is no formal secret rotation or incident-response procedure.

## 7. Browser review

The browser is ready for a single-process private MVP and supports both manual UI control and TILLU-proposed actions.

It is not yet production-durable because it lacks:

- restart recovery;
- multiple tabs;
- semantic/accessible target snapshots;
- session TTL cleanup;
- download handling and quarantine;
- persistent cookies with explicit owner controls;
- remote browser/session affinity for scaling;
- robust CAPTCHA/login/MFA handling;
- action recordings and replay-safe idempotency.

Recommended next design: Playwright workers behind a session service, Redis/Postgres session metadata, sticky routing, encrypted storage state, explicit TTLs, and accessibility-tree target IDs instead of raw selectors where possible.

## 8. Knowledge/RAG review

The current local retrieval pipeline is useful for ordinary PDFs: bounded parsing, chunks, lexical scoring, page citations, and document widgets.

It is not yet a large-file knowledge system. Missing pieces:

- asynchronous ingestion jobs;
- OCR for scanned documents;
- table/formula extraction;
- embeddings and pgvector search;
- hybrid fusion and reranking;
- chunk/parser versioning in active retrieval;
- deletion/reindex consistency tests;
- provenance and extraction-quality indicators;
- isolated parser workers.

## 9. Automation and integration review

Automations have schedules, run history, source gathering, model synthesis, and queue foundations. Gmail and WhatsApp adapters follow the correct optional-integration rule.

Still required:

- production-only durable claims and retries;
- cancellation and dead-letter handling;
- idempotent external effects;
- trigger/action composition;
- quiet hours and notification delivery;
- Gmail OAuth connection UI and token lifecycle;
- WhatsApp webhook verification, templates, receipts, and opt-in tracking.

## 10. Frontend and UX review

### Strong points

- one unified Assistant workspace;
- Chat, Browser, Notes, and Canvas coexist;
- typed result widgets and approvals are visible;
- light/dark themes;
- tool and cycle visibility;
- server results remain authoritative.

### Weak points

- giant component file;
- no streaming state machine;
- limited accessibility testing;
- browser controls still expose CSS selectors;
- no robust optimistic-update/rollback framework;
- no offline conflict-resolution UI;
- mobile and desktop shells lack parity;
- no frontend end-to-end test suite.

## 11. Documentation accuracy

Some documentation is stale. `ARCHITECTURE.md` and `FEATURE_STATUS.md` still describe SQLite as the active production route repository and canvas persistence/browser screenshots as incomplete. Code now contains a production Supabase repository boundary, persistent canvases, expanded action tools, and screenshot UI. Documentation should be generated or checked against a capability manifest to reduce drift.

## 12. Recommended execution order

### P0 — prove production safety

1. Apply migrations through `007_production_repository.sql` to a real Supabase test project.
2. Add live owner/non-owner RLS tests.
3. Add repository contract tests for SQLite and Supabase.
4. Verify Storage upload/download/delete and queue RPCs.
5. Remove any production dependence on process caches.
6. Add action-registry parity tests and idempotency tests.

### P1 — unify the harness

1. Replace separate read/action definitions with one typed capability registry.
2. Move proposal execution out of `main.py` into an approval service.
3. Generate `/api/tools`, model schemas, UI previews, and audit rules from that registry.
4. Add semantic entity resolution and confirmation when confidence is low.
5. Persist complete rich-message and run metadata.

### P2 — reliability and UX

1. Add SSE streaming, tool events, cancellation, and reconnect.
2. Add durable run checkpoints and continuation.
3. Split backend routes/services and frontend feature modules.
4. Add structured logs, traces, metrics, and error correlation IDs.
5. Add browser session TTLs, cleanup, and remote-worker/session-affinity design.

### P3 — intelligence and ecosystem

1. Build OCR/hybrid pgvector ingestion workers.
2. Add controlled long-term memory with review/delete controls.
3. Complete notifications and automation delivery.
4. Complete Gmail OAuth and WhatsApp webhooks.
5. Bring mobile and desktop shells to feature parity.

## Final assessment

TILLU's architecture is **directionally correct and unusually capable for an MVP**. The essential safety decisions—server-owned tools, bounded reasoning, explicit approvals, owner isolation, deterministic fallbacks, and real browser execution—are good.

The main architectural risk is no longer lack of features; it is **feature growth outrunning system unification and operational proof**. The next phase should prioritize one typed capability registry, live Supabase/RLS verification, durable runs, browser/session reliability, metadata persistence, and broad automated testing rather than adding many more isolated endpoints.
