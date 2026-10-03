# TILLU deployment manifests

The accepted production topology is defined by `docs/ADR-001_HOSTING_TOPOLOGY.md`.

- `brain/render.yaml` — deploy in Render account A as the public Brain API.
- `runtime/render.yaml` — deploy in Render account B as the Docker Runtime/worker service.
- `../apps/web/vercel.json` — deploy `apps/web` to Vercel. See `frontend/README.md` for full Vercel and Docker self-host instructions, required env vars, security headers, and post-deploy CORS step.

Both Render services may share the `apps/api` image, but they have distinct `SERVICE_ROLE` values, secrets, health requirements, and operational responsibilities. They coordinate through Supabase and authenticated internal RPC, never SQLite or process memory.

The repository-root `render.yaml` intentionally defaults to Brain only. Do not use it to collapse Brain and Runtime into one service.
