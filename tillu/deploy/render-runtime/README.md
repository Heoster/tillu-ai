# deploy/render-runtime — TILLU Runtime (Render account B)

This folder is the complete deployment package for the **Runtime** service. Point a Render Blueprint at `deploy/render-runtime/render.yaml` and Render will build and run the Runtime (Playwright) image directly from this config.

## What this folder contains

| File | Purpose |
|------|---------|
| `render.yaml` | Render Blueprint for the Runtime service (account B) |
| `Dockerfile` | Playwright-capable image — includes Chromium dependencies |
| `.dockerignore` | Excludes venv, caches, .db files, tests from the build context |
| `env.runtime.example` | All env vars the Runtime service reads, with comments |
| `README.md` | This file |

The Docker build context is `./apps/api` (the `dockerContext` field in `render.yaml`). The `app/` source and `requirements.txt` are pulled from there — this folder holds only the deployment config layer on top.

## How to deploy (Render account B)

1. In Render account B → **Blueprints** → **New Blueprint Instance**.
2. Connect your repository and set the **Blueprint file path** to `deploy/render-runtime/render.yaml`.
3. Render will detect the `tillu-runtime` service and start the first deploy.
4. In the service's **Environment** tab, fill in every `sync: false` variable:

### Required env vars

| Variable | Notes |
|----------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role key |
| `OWNER_USER_ID` | Heoster's Supabase `auth.users` UUID |
| `CORS_ORIGINS` | Exact Vercel origin, e.g. `https://tillu.vercel.app` |
| `PUBLIC_APP_URL` | Same as CORS_ORIGINS |
| `TILLU_INTERNAL_SECRET` | Must match the Brain service's `TILLU_INTERNAL_SECRET` |
| `CRON_SECRET` | Protect `/api/internal/*` cron endpoints |
| `BACKUP_ENCRYPTION_KEY` | Encrypt at-rest backups |
| `VAPID_PUBLIC_KEY` | PWA Web Push (generate with `npx web-push generate-vapid-keys`) |
| `VAPID_PRIVATE_KEY` | PWA Web Push private key |
| `VAPID_SUBJECT` | e.g. `mailto:heoster@example.com` |

See `env.runtime.example` for the full list including optional integrations.

## Local build and run

```bash
# Build (run from repo root — context is apps/api)
docker build -f deploy/render-runtime/Dockerfile apps/api -t tillu-runtime

# Run
docker run --rm -p 8000:8000 --env-file deploy/render-runtime/env.runtime.example tillu-runtime
```

Health check: `curl http://localhost:8000/api/health/live`

> The Playwright/Chromium base image is large (~1.5 GB). The first pull takes a few minutes on initial deploy.

## Relationship to other manifests

- `deploy/runtime/render.yaml` is the original manifest pointing at `apps/api/Dockerfile`. It remains valid.
- This folder (`deploy/render-runtime/`) bundles all Runtime deployment files together for clarity. Its `render.yaml` points `dockerfilePath` at `./deploy/render-runtime/Dockerfile` instead, so both approaches build the same image.
- For the Brain service, see `deploy/render-brain/`.
