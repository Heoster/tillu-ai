# Hosting layout

The repository is arranged so each hosting platform has one clear entry point. The accepted production topology is defined in `docs/ADR-001_HOSTING_TOPOLOGY.md`.

```text
tillu/
├── render.yaml                         # Root Render Blueprint: Brain only (Render account A)
├── deploy/
│   ├── README.md                        # Deployment manifest index
│   ├── brain/
│   │   └── render.yaml                  # Canonical Brain Render Blueprint (account A)
│   ├── runtime/
│   │   └── render.yaml                  # Runtime Render Blueprint (account B)
│   ├── backend/
│   │   └── README.md                    # Both Dockerfiles and both Render services explained
│   └── frontend/
│       └── README.md                    # Vercel, env vars, Docker self-host, CORS post-deploy
├── apps/
│   ├── api/
│   │   ├── Dockerfile                   # Runtime image: Playwright + Chromium (SERVICE_ROLE=runtime)
│   │   ├── Dockerfile.brain             # Brain image: slim FastAPI (SERVICE_ROLE=brain)
│   │   ├── .dockerignore
│   │   ├── .env.example                 # Backend configuration contract
│   │   ├── requirements.txt
│   │   └── app/
│   └── web/
│       ├── vercel.json                  # Vercel: Vite build, SPA routing, security headers
│       ├── Dockerfile                   # Optional Docker self-host for the PWA
│       ├── nginx.conf                   # nginx config for Docker self-host
│       ├── .env.production.example
│       ├── package.json
│       └── src/
├── supabase/
│   └── migrations/                      # Apply 001–016 in numeric order
├── docs/
│   ├── ADR-001_HOSTING_TOPOLOGY.md      # Topology decision record (authoritative)
│   ├── HOSTING_LAYOUT.md                # This file
│   ├── DEPLOYMENT.md                    # Step-by-step deployment guide
│   └── GETTING_STARTED.md               # Local development setup
└── .github/
    └── workflows/
        ├── ci.yml                       # Web build + API tests on push/PR
        ├── refresh-digest.yml           # Scheduled digest refresh (calls Brain)
        └── deploy-check.yml             # Post-deploy health check (Brain + Runtime)
```

## Render — two services, two accounts

Per ADR-001, the backend is split into two independent Render services:

### Brain (Render account A)

- **Blueprint:** `deploy/brain/render.yaml` (also mirrored at repository root `render.yaml`)
- **Dockerfile:** `apps/api/Dockerfile.brain` (slim image, no Playwright)
- **SERVICE_ROLE:** `brain`
- **Responsibilities:** public API, LangGraph orchestration, model routing, memory reasoning, planning, approvals, synthesis, SSE
- **Required secrets:** Supabase keys, owner identity, CORS, Honcho, at least one model key, Cloudflare credentials, RPC secret

### Runtime (Render account B)

- **Blueprint:** `deploy/runtime/render.yaml`
- **Dockerfile:** `apps/api/Dockerfile` (Playwright-capable image)
- **SERVICE_ROLE:** `runtime`
- **Responsibilities:** Playwright/browser execution, heavy file handling, durable workers, cron, retries, recovery, backups
- **Required secrets:** Supabase keys, owner identity, CORS, VAPID push keys, internal secret

Brain and Runtime coordinate through Supabase and authenticated internal RPC. They must never share process memory, local disk, or SQLite.

## Vercel

Import the repository and set **Root Directory** to `apps/web`. Vercel reads `apps/web/vercel.json`. Set `VITE_API_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY`. After deploy, add the Vercel origin to Brain's `CORS_ORIGINS`. See `deploy/frontend/README.md` for full instructions.

## Supabase

Create a private project, apply `supabase/migrations/001` through `016` in order, disable public onboarding, and copy the project URL and anon key to Vercel and all server keys only to Render services.

## GitHub Actions

- `ci.yml`: runs on every push/PR — builds the web app and runs API tests.
- `refresh-digest.yml`: scheduled — calls Brain's internal digest refresh endpoint using `TILLU_API_URL` and `TILLU_CRON_SECRET` secrets.
- `deploy-check.yml`: runs on push to `main` and `workflow_dispatch` — performs a curl liveness check against both Brain (`TILLU_BRAIN_URL`) and Runtime (`TILLU_RUNTIME_URL`) with `continue-on-error: true`.

## Deployment blocker

Several core routes still use SQLite. Render's filesystem is not the production source of truth. Do not store irreplaceable data until the Postgres repository migration and backups are completed.
