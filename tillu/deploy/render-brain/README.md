# deploy/render-brain — TILLU Brain (Render account A)

This folder is the complete deployment package for the **Brain** service. Point a Render Blueprint at `deploy/render-brain/render.yaml` and Render will build and run the Brain image directly from this config.

## What this folder contains

| File | Purpose |
|------|---------|
| `render.yaml` | Render Blueprint for the Brain service (account A) |
| `Dockerfile.brain` | Slim Python 3.13 image — no Playwright, no Chromium |
| `.dockerignore` | Excludes venv, caches, .db files, tests from the build context |
| `env.brain.example` | All env vars the Brain service reads, with comments |
| `README.md` | This file |

The Docker build context is `./apps/api` (the `dockerContext` field in `render.yaml`). The `app/` source and `requirements.txt` are pulled from there — this folder holds only the deployment config layer on top.

## How to deploy (Render account A)

1. In Render account A → **Blueprints** → **New Blueprint Instance**.
2. Connect your repository and set the **Blueprint file path** to `deploy/render-brain/render.yaml`.
3. Render will detect the `tillu-brain` service and start the first deploy.
4. In the service's **Environment** tab, fill in every `sync: false` variable:

### Required env vars

| Variable | Notes |
|----------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role key (never expose to browser) |
| `OWNER_USER_ID` | Heoster's Supabase `auth.users` UUID |
| `CORS_ORIGINS` | Exact Vercel origin, e.g. `https://tillu.vercel.app` |
| `PUBLIC_APP_URL` | Same as CORS_ORIGINS (the Vercel URL) |
| `RUNTIME_INTERNAL_URL` | Internal URL of the Runtime service on Render account B |
| `TILLU_INTERNAL_SECRET` | Shared secret with Runtime — generate with `openssl rand -hex 32` |
| `CRON_SECRET` | Protect `/api/internal/*` cron endpoints |
| `RPC_CAPABILITY_SECRET` | Protect inter-service RPC |
| `BACKUP_ENCRYPTION_KEY` | Encrypt at-rest backups |
| `HONCHO_API_KEY` | Honcho long-term memory API key |
| At least one of: `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`+`CLOUDFLARE_API_TOKEN` | Model provider |

See `env.brain.example` for the full list.

## Local build and run

```bash
# Build (run from repo root — context is apps/api)
docker build -f deploy/render-brain/Dockerfile.brain apps/api -t tillu-brain

# Run
docker run --rm -p 8000:8000 --env-file deploy/render-brain/env.brain.example tillu-brain
```

Health check: `curl http://localhost:8000/api/health/live`

## Relationship to other manifests

- `deploy/brain/render.yaml` and the repo-root `render.yaml` are the original manifests pointing at `apps/api/Dockerfile.brain`. They remain valid.
- This folder (`deploy/render-brain/`) bundles all Brain deployment files together for clarity. Its `render.yaml` points `dockerfilePath` at `./deploy/render-brain/Dockerfile.brain` instead, so both approaches build the same image.
- For the Runtime service, see `deploy/render-runtime/`.
