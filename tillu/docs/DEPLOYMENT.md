# Deployment

## Recommended private topology (ADR-001)

- **Vercel:** React PWA (`apps/web`)
- **Render account A — Brain:** FastAPI orchestration service; LangGraph, model routing, memory, planning, approvals, SSE. Uses `apps/api/Dockerfile.brain` (slim, no Playwright). Blueprint: `deploy/brain/render.yaml` (also at repo root `render.yaml`).
- **Render account B — Runtime:** Playwright/browser execution, durable workers, cron, retries, recovery, backups. Uses `apps/api/Dockerfile` (Playwright-capable). Blueprint: `deploy/runtime/render.yaml`.
- **Supabase:** Heoster authentication, Postgres source of truth, Storage, durable queues, leases, checkpoints.
- **GitHub Actions:** CI, protected scheduled digest refresh, post-deploy health checks.

See `docs/ADR-001_HOSTING_TOPOLOGY.md` for the authoritative topology decision and invariants.

## Required production settings

### Brain (Render account A)

Set `ENVIRONMENT=production`, `SERVICE_ROLE=brain`, all Supabase keys, `OWNER_USER_ID` (or `OWNER_EMAIL`), exact `CORS_ORIGINS`, `PUBLIC_APP_URL`, `RUNTIME_INTERNAL_URL`, `TILLU_INTERNAL_SECRET`, `CRON_SECRET`, `RPC_CAPABILITY_SECRET`, `BACKUP_ENCRYPTION_KEY`, Honcho credentials, at least one AI provider key, and Cloudflare credentials.

### Runtime (Render account B)

Set `ENVIRONMENT=production`, `SERVICE_ROLE=runtime`, all Supabase keys, `OWNER_USER_ID` (or `OWNER_EMAIL`), exact `CORS_ORIGINS`, `PUBLIC_APP_URL`, `TILLU_INTERNAL_SECRET`, `CRON_SECRET`, `BACKUP_ENCRYPTION_KEY`, `BROWSER_HEADLESS=true`, and VAPID push keys.

Production startup intentionally fails when mandatory identity/model/CORS configuration is incomplete.

## API images

`apps/api/Dockerfile.brain` — slim Brain image without Playwright. Used by `deploy/brain/render.yaml`. One web worker; orchestration-focused, low memory.

`apps/api/Dockerfile` — Playwright-capable Runtime image. Used by `deploy/runtime/render.yaml`. Includes Chromium dependencies. One web worker to avoid routing requests away from process-local browser sessions. This is an alpha constraint; production browser sessions should move to a durable remote browser service before horizontal scaling.

## Web deployment

Set `VITE_API_URL` to the HTTPS Brain URL ending in `/api`. Configure `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Never place backend provider or service-role secrets in Vercel. After deploy, add the Vercel origin to Brain's `CORS_ORIGINS`.

## Database migrations

Apply Supabase migrations in order before starting production. Key migrations:
- `005_execution_hardening.sql` — durable job leasing, automation occurrence uniqueness, quota accounting.
- `006_private_assistant_complete.sql` — tasks, calendar, research, browser history, chunks, settings, proposals, checkpoints, missing metadata/RLS.
- Migrations 007–016 — additional schema hardening and feature additions.

Applying migrations does not by itself prove production readiness; verify every deployed route and RLS policy against the configured Supabase project.

## Scheduled operations

Protect `/api/internal/refresh-digest` and `/api/internal/run-due-automations` with `CRON_SECRET`. Set `TILLU_API_URL` and `TILLU_CRON_SECRET` as GitHub repository secrets for `.github/workflows/refresh-digest.yml`. Production due runs enqueue durable jobs; workers claim with leases and `SKIP LOCKED`.

## Post-deploy health check

Add `TILLU_BRAIN_URL` and `TILLU_RUNTIME_URL` as GitHub repository secrets. `.github/workflows/deploy-check.yml` runs on push to `main` and performs a curl liveness check against both `TILLU_BRAIN_URL/api/health/live` and `TILLU_RUNTIME_URL/api/health/live` with `continue-on-error: true` to tolerate cold starts.

## Release checklist

- Verify only Heoster's account can access authenticated routes.
- Verify exact CORS and proxy client-IP behavior.
- Test Postgres/RLS and storage policies.
- Test queue retries, lease expiry and duplicate cron calls.
- Test provider 429/circuit fallback.
- Test controlled browser network policy.
- Configure backups and perform a restore drill.
- Confirm optional integrations show disabled rather than connected when unconfigured.
- Run backend tests, compile, frontend build and end-to-end smoke tests.

## Current release boundary

The code is suitable for private alpha evaluation. Hosted use with irreplaceable data is blocked by incomplete Postgres repository migration and backup validation. See `FEATURE_STATUS.md`.
