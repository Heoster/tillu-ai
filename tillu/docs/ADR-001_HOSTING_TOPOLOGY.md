# ADR-001: Fixed production hosting topology

**Status:** Accepted  
**Owner:** Heoster  
**Scope:** TILLU production deployment

## Decision

TILLU uses three independently deployed surfaces:

1. **Vercel UI** (`apps/web`) — browser-safe React client and Supabase anon authentication only.
2. **Render account/service A: Brain** (`SERVICE_ROLE=brain`) — public API, LangGraph orchestration, model routing, memory reasoning, planning, approvals, synthesis, and SSE.
3. **Render account/service B: Runtime** (`SERVICE_ROLE=runtime`) — Docker/Playwright, heavy files, browser execution, durable workers, cron, retries, recovery, backups, and delegate execution.
4. **Supabase** — Auth, Postgres, Storage, durable queues, leases, checkpoints, and production source of truth.

The UI has one primary API origin: Brain. Brain and Runtime must never coordinate through process memory or SQLite. Cross-service state goes through Supabase; immediate internal requests use authenticated, capability-scoped RPC. SQLite remains development/test-only.

## Invariants preventing future architectural drift

- Do not merge Brain and Runtime into one production responsibility, even if they currently share a source image.
- Do not add backend secrets to Vercel or browser bundles.
- Do not make Runtime the browser's general public API.
- Do not introduce shared local disk or SQLite between Render services.
- Do not depend on an in-memory scheduler, browser session, delegate task, or queue surviving a restart.
- Do not let internal RPC bypass typed capability validation, owner checks, idempotency, or approval policy.
- Reads may run automatically; consequential writes and external effects require per-run approval.
- Production health must distinguish liveness, readiness, and authenticated dependency diagnostics.
- Optional integrations must fail closed and must not block core startup unless explicitly promoted to required.
- Changes to this topology require a new superseding ADR approved by Heoster; silently changing this ADR is prohibited.

## Deployment manifests

- Brain: `deploy/brain/render.yaml`
- Runtime: `deploy/runtime/render.yaml`
- Vercel: `apps/web/vercel.json`
- Production migrations: `supabase/migrations`

## Health contract

- `GET /api/health` — public identity/build summary.
- `GET /api/health/live` — public process liveness only.
- `GET /api/health/ready` — public role-specific readiness; HTTP 503 when required configuration is absent.
- `GET /api/health/dependencies` — authenticated detailed dependency state; never returns credentials.
- `GET /api/production-readiness` — authenticated release gate and honest unverified-service statuses.

Configured is not equivalent to live-verified.
