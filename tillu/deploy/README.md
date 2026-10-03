# TILLU deployment manifests

The accepted production topology is defined by `docs/ADR-001_HOSTING_TOPOLOGY.md`.

## Render — two self-contained deploy packages

- `render-brain/` — **Render account A (Brain)**. Contains `render.yaml`, `Dockerfile.brain`, `.dockerignore`, `.env.brain.example`, and a README. Point a Blueprint here to deploy the Brain service in one step.
- `render-runtime/` — **Render account B (Runtime)**. Contains `render.yaml`, `Dockerfile`, `.dockerignore`, `.env.runtime.example`, and a README. Point a Blueprint here to deploy the Runtime (Playwright) service in one step.

## Original per-manifest references

- `brain/render.yaml` — original Brain Blueprint (points at `apps/api/Dockerfile.brain`). Still valid.
- `runtime/render.yaml` — original Runtime Blueprint (points at `apps/api/Dockerfile`). Still valid.
- `../apps/web/vercel.json` — deploy `apps/web` to Vercel. See `frontend/README.md` for full Vercel and Docker self-host instructions, required env vars, security headers, and post-deploy CORS step.

Both Render services have distinct `SERVICE_ROLE` values, secrets, health requirements, and operational responsibilities. They coordinate through Supabase and authenticated internal RPC, never SQLite or process memory.

The repository-root `render.yaml` intentionally defaults to Brain only. Do not use it to collapse Brain and Runtime into one service.
