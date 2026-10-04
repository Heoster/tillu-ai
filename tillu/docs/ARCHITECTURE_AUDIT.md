# TILLU Architecture Security & Reliability Audit

**Identity:** TILLU is built by and for Heoster.  
**Deployment model:** Private, single-owner personal system; it is not a public multi-user product.  
**Audit date:** 2026-09-30  
**Scope:** Current repository implementation, not the intended architecture  
**Revised conclusion:** Multi-tenant SaaS readiness is not a product requirement. The relevant release goal is a securely authenticated, single-owner deployment that rejects every account except Heoster's configured Supabase identity. Findings about durability, unauthorized-account access, SSRF, approvals, files, queues, quotas, and data loss remain applicable. Cross-tenant findings are retained as defense-in-depth analysis, not as a requirement to support multiple users.

> **Remediation update:** Plan ownership, conversation injection, redirect handling, path disclosure, bounded PDF parsing, durable queue schema/worker, automation occurrence idempotency, usage accounting, owner-only auth, adaptive provider cooldown/circuit breakers, and typed action approvals have received implementation work. Production SQLite repositories, process-global job/progress state, fully pinned outbound networking, comprehensive security tests, hybrid RAG, durable browser sessions and backup validation remain unresolved. See `FEATURE_STATUS.md` for the current source of truth.

## P0 — release blockers

### 1. Production still persists core data in local SQLite

The API requires Supabase variables in production, but nearly every repository call still uses `database.py` and `tillu_demo.db`. Supabase is used mainly for token validation and optional PDF upload. Conversations, tasks, notes, automations, plans, runs, sources, calendar, progress, and audit events remain local.

**Impact:** Render's ephemeral filesystem can erase data. Multiple API replicas have independent state. Authenticated users may see inconsistent results. Backups, Realtime, and RLS do not protect the actual data being used.

**Required fix:** Create a repository interface with complete Postgres/Supabase and SQLite implementations. Production startup must instantiate only Postgres repositories. Remove all direct `database.py` imports from routes and orchestration.

### 2. Several user-data endpoints are unauthenticated or globally scoped

Current examples include syllabus progress, job listing, individual jobs, and audit listing. `PROGRESS`, `JOBS`, and `PLANS` are process-global dictionaries. Job objects do not contain an owner. `load_progress()` is not user-scoped.

**Impact:** Cross-user disclosure and mutation. One user can inspect jobs or progress created by another user. Data also leaks across local-development identities and future cloud users.

**Required fix:** Add `user_id` to every job/progress/plan record and require `current_user` on every non-public route. Eliminate global dictionaries as sources of truth. Add object-level authorization tests.

### 3. In-memory plan approval can bypass ownership checks

Persisted plans check `stored["user_id"]`, but a plan found in global `PLANS` is accepted without confirming its owner. The plan object itself has no owner.

**Impact:** A user who obtains or guesses a live plan ID may approve another user's action.

**Required fix:** Never approve from global memory. Load the plan through an owner-filtered repository query, lock it, check its current state, and atomically transition it using compare-and-set semantics.

### 4. Conversation IDs permit cross-user message injection

`ensure_conversation()` uses `ON CONFLICT(id) DO UPDATE` without checking the owner. `add_message()` then inserts into the supplied conversation ID. Although reading is owner-filtered, a malicious user can submit another conversation ID and append messages to it.

**Impact:** Integrity attack against another user's conversation and future model context.

**Required fix:** Generate conversation IDs server-side, or verify ownership before every continuation. Use a foreign key and an atomic owner-scoped insert. Reject conflicts belonging to another user.

### 5. SSRF checks are vulnerable to redirect and DNS-rebinding gaps

`webreader.py` and `downloads.py` validate the initial hostname, then use a separate HTTP client with redirects enabled. Redirect destinations are not revalidated. DNS is resolved once for policy and again during connection.

**Impact:** A public URL can redirect to metadata services, private networks, localhost, or internal control planes. DNS rebinding may also change the destination after validation.

**Required fix:** Disable automatic redirects. Resolve and connect through a pinned validated address, validate every redirect hop, reject non-public ranges for IPv4 and IPv6, cap redirects, and add comprehensive SSRF tests.

### 6. Durable jobs are not actually durable

Background work uses `asyncio.create_task()` and in-process dictionaries. A restart terminates active jobs. Loading job rows after restart does not resume them. Multiple workers can duplicate work.

**Impact:** Lost downloads, stuck plans, false completion state, and duplicate external effects.

**Required fix:** Use a real queue/lease model in Postgres, Temporal, Trigger.dev, or Redis-backed workers. Add heartbeats, attempt counts, idempotency keys, lease expiry, cancellation, and restart recovery.

## P1 — high priority

### 7. Automation execution has race and duplication risks

The due query does not claim rows. Two cron calls or workers can run the same automation. There is no unique scheduled-occurrence key. Runs execute sequentially and can exceed request timeouts.

**Fix:** Atomically claim due automations with `FOR UPDATE SKIP LOCKED`; store a unique `(automation_id, scheduled_for)` key; enqueue work instead of executing it inside the cron HTTP request.

### 8. Cron schedules are not validated safely

`next_run(body.schedule)` executes during creation and invalid expressions can produce an internal error. Schedules are interpreted in server/UTC time with no per-user timezone.

**Fix:** Validate cron in Pydantic, limit frequency, store IANA timezone, calculate DST-aware execution, and reject schedules more frequent than policy permits.

### 9. Files expose internal filesystem paths

File APIs return the absolute server `path`. In local mode this reveals deployment structure. Files remain on ephemeral disk even when metadata claims cloud readiness.

**Fix:** Never serialize internal paths. Return stable file IDs and signed download URLs. Upload directly or reliably to object storage before acknowledging success.

### 10. PDF processing lacks anti-bomb controls

The upload has a byte limit but no page-count, decompression, object-count, recursion, parse-time, or CPU limit. Text extraction occurs in the application worker.

**Fix:** Process PDFs in an isolated worker with memory/CPU/time limits; cap pages and extracted characters; scan malware; reject encrypted/malformed files; add OCR as a separate bounded job.

### 11. Rate limiting is process-local and proxy-sensitive

The limiter is an in-memory deque. It resets on restart and is not shared across workers. The Docker command trusts forwarded headers from all sources, allowing client-IP spoofing in some deployments.

**Fix:** Use Redis/Postgres-backed limits by user and IP. Trust forwarding headers only from the platform proxy. Add separate expensive-operation quotas.

### 12. Supabase service-role usage has no narrow repository boundary

The cloud adapter uses the service-role key, bypassing RLS. Current methods accept caller-supplied user IDs from application code.

**Fix:** Isolate privileged operations, derive user IDs only from verified sessions, validate object ownership again, and prefer user-scoped Supabase clients where practical.

### 13. Search and model quota governance is incomplete

Search fallback can call multiple paid providers after failures. There are no per-user budgets, daily caps, cost accounting, or circuit breakers for search services. Model routing also lacks durable quota counters.

**Fix:** Add quota ledger, per-provider budget, user/day limits, request deduplication, cache, latency/cost scoring, and an explicit maximum fallback count.

### 14. Tool routing is keyword-based, not a complete policy planner

The LangGraph selects tools with substring checks. It can miss intent, select irrelevant tools, and cannot request structured clarification. Write tools are outside the registry and the approval graph is hard-coded to create a PYQ job regardless of plan type.

**Fix:** Introduce typed intents, structured tool proposals, plan schemas per action, policy evaluation, clarification nodes, and action-specific approved executors. Never map every approval to `pyq_download`.

### 15. Context memory is not semantic and can cross relevance boundaries

Conversation memory keeps only recent characters. There is no durable summary, fact provenance, preference expiry, or semantic selection. Tool context is capped by characters rather than model tokens.

**Fix:** Add token-aware budgeting, conversation summaries, user-approved long-term memories, embeddings with tenant filters, provenance, deletion, and contradiction handling.

## P2 — medium priority

### 16. RAG is lexical-only and lacks ingestion lifecycle

The improved BM25-style retrieval is useful but has no embeddings, OCR, table extraction, chunk versioning, parser version, re-index status, or deletion cascade. `document_chunks` lacks enforced ownership and file foreign keys in SQLite.

**Fix:** Add ingestion states, parser/chunk versions, pgvector hybrid retrieval, reranking, OCR, table-aware parsing, tenant filters, and cascade deletion.

### 17. Search citations are not fully verified

The post-check only removes citation numbers not present in the result list. It does not verify whether the cited source supports each claim.

**Fix:** Add claim extraction and entailment checking, citation-to-claim mapping, duplicate-domain controls, recency metadata, and source-quality ranking.

### 18. Browser chat trusts client-supplied page text

`/api/browser/ask` accepts title, URL, and content from the browser rather than loading an immutable server snapshot.

**Impact:** Users can attribute fabricated text to a real URL. This is not a cross-user security issue, but it undermines provenance.

**Fix:** Pass a server-generated snapshot ID. Retrieve stored content and URL server-side.

### 19. External images create privacy leakage

The Discover UI loads publisher-provided image URLs directly, exposing the user's IP, referrer behavior, and browser to third-party image hosts.

**Fix:** Remove images or proxy/cache them through a validated image service with content-type and size checks.

### 20. Canvas claims exceed persistence behavior

The schema supports `canvas_data`, but the canvas exports PNG locally and does not save/load drawings to notes. Undo stores complete data URLs in browser memory.

**Fix:** Persist vector strokes rather than raster snapshots, enforce size limits, autosave revisions, and move large snapshots to object storage.

### 21. Offline outbox is unencrypted and conflict handling is incomplete

Progress mutations are stored in `localStorage`; conflict resolution and idempotency are limited. Sensitive notes are not supported offline safely.

**Fix:** Use IndexedDB/SQLite, encrypt sensitive caches where feasible, persist accepted mutation IDs, add server versions, and define deterministic conflict rules.

### 22. Authentication bootstrap fails open visually

If `/api/config` fails, the frontend chooses local UI mode. The backend still protects production routes, so this does not bypass API auth, but it produces confusing behavior and may expose cached UI.

**Fix:** In production builds, fail closed to an error/retry screen unless configuration is positively loaded.

### 23. Audit logs are incomplete and not tamper-evident

Some reads/writes are unaudited; audit retrieval is not clearly owner-scoped in the current local path. Logs have no retention, signature chain, or export policy.

**Fix:** Centralize audit middleware, include request/run IDs and actor, redact inputs, make logs append-only, define retention, and restrict retrieval.

### 24. Error handling may leak internal behavior

Some upstream exception types are returned, while many frontend errors are swallowed or shown through `alert()`. There is no centralized error envelope or error monitoring.

**Fix:** Add structured error codes, safe messages, Sentry/OpenTelemetry, frontend error boundaries, and user-facing retry states.

### 25. Automated tests are far below production needs

Five unit tests do not cover authentication, ownership, RLS, SSRF redirects, uploads, queues, approvals, automation races, provider fallback, migrations, or end-to-end flows.

**Fix:** Add integration tests with Postgres/Supabase, security regression tests, concurrent-worker tests, Playwright UI tests, mobile/desktop smoke tests, and backup/restore drills.

## Additional design gaps

- No backup/restore procedure has been exercised.
- No data export/account deletion workflow.
- No privacy policy, consent, retention, or provider-data-use controls.
- No secret rotation workflow.
- No malware scanning or content moderation policy.
- No accessibility audit.
- No model-evaluation suite or prompt-version tracking.
- No SLOs, tracing, metrics, alerting, or incident response.
- No Android/Windows signing and update channel.
- Firecrawl/You/Parallel/Tavily cost and terms can change; runtime budgets must not assume perpetual free access.

## Recommended remediation order

### Milestone A — tenant isolation

1. Replace production SQLite with Postgres repositories.
2. Add owner fields and auth dependencies to every route.
3. Remove global user-data dictionaries.
4. Fix conversation and plan ownership bugs.
5. Add cross-tenant integration tests.

### Milestone B — execution safety

1. Replace in-process jobs with durable queue workers.
2. Make plan approval atomic and action-specific.
3. Add idempotency and automation occurrence locks.
4. Harden SSRF and file processing.
5. Add shared rate limits and quotas.

### Milestone C — knowledge quality

1. Add versioned hybrid pgvector RAG.
2. Store immutable browser snapshots.
3. Add claim/citation verification.
4. Add token-aware memory and user-controlled long-term facts.

### Milestone D — operations

1. Observability, SLOs, alerts, and cost dashboards.
2. Backups and restore drills.
3. Security testing and dependency scanning.
4. Privacy, retention, export, and deletion.
5. Signed Android/Windows releases and staged updates.

## Release decision

**Current verdict: CONDITIONAL GO for Heoster's private single-owner alpha; public access is out of scope.**  
Before hosted use, configure `OWNER_USER_ID` or `OWNER_EMAIL`, keep signup/invitations closed, and verify non-owner rejection. Local SQLite still creates data-loss and multi-replica consistency risk even for one owner, so sensitive or irreplaceable data should wait for the production Postgres repository and tested backups. There is no plan to invite external users.
