# Backend hosting entry

This directory is the hosting control plane for the real backend source in `apps/api`; it contains no duplicate or mock backend.

## Two Render services, two Dockerfiles

The backend is split across two independent Render accounts/services per ADR-001:

| Service | Render account | Blueprint manifest | Dockerfile | SERVICE_ROLE |
|---------|---------------|-------------------|------------|--------------|
| **Brain** | Account A | `deploy/brain/render.yaml` | `apps/api/Dockerfile.brain` | `brain` |
| **Runtime** | Account B | `deploy/runtime/render.yaml` | `apps/api/Dockerfile` | `runtime` |

### apps/api/Dockerfile.brain
Slim image for the Brain service: public API, LangGraph orchestration, model routing, memory reasoning, planning, approvals, synthesis, and SSE. Does not include Playwright or Chromium.

### apps/api/Dockerfile
Playwright-capable image for the Runtime service: Docker/browser execution, heavy file handling, durable workers, cron, retries, recovery, and backups. Includes Chromium dependencies.

## Deploying Brain (Render account A)

1. In Render account A, create a Blueprint and point it to the repository root — Render will pick up the root `render.yaml` (which is the canonical Brain blueprint).
2. Alternatively, point directly to `deploy/brain/render.yaml`.
3. Configure all `sync: false` env vars in the Render dashboard: Supabase keys, `OWNER_USER_ID`, `CORS_ORIGINS`, `PUBLIC_APP_URL`, `RUNTIME_INTERNAL_URL`, `TILLU_INTERNAL_SECRET`, `CRON_SECRET`, `RPC_CAPABILITY_SECRET`, Honcho keys, at least one model API key, and Cloudflare credentials.

## Deploying Runtime (Render account B)

1. In Render account B, create a Blueprint and point it to `deploy/runtime/render.yaml`.
2. Configure all `sync: false` env vars: Supabase keys, `OWNER_USER_ID`, `CORS_ORIGINS`, `PUBLIC_APP_URL`, `TILLU_INTERNAL_SECRET`, `CRON_SECRET`, VAPID push keys.

## Production requirements

- Apply `supabase/migrations` in numeric order (001–016) before starting production.
- Brain and Runtime coordinate through Supabase and authenticated internal RPC only — never SQLite or shared memory.
- `OWNER_USER_ID`, exact Vercel `CORS_ORIGINS`, `PUBLIC_APP_URL`, Supabase keys, and at least one model key are mandatory for production startup.

## Local verification

```bash
# Brain image
docker build -f apps/api/Dockerfile.brain apps/api -t tillu-brain

# Runtime image (Playwright)
docker build -f apps/api/Dockerfile apps/api -t tillu-runtime
```
