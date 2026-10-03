# deploy/render-runtime — TILLU Runtime (Render account B)

This folder is a **fully self-contained** deployment package for the Runtime service. It contains everything the Docker build needs — no files are resolved from `apps/api` or anywhere else in the repository at build time.

## Folder structure

```
deploy/render-runtime/
├── app/                     # Full FastAPI application source (copied from apps/api/app/)
│   ├── main.py              # FastAPI entry point, all routes
│   ├── config.py            # Settings (pydantic-settings, reads from env)
│   ├── auth.py              # Supabase JWT auth
│   ├── browser_control.py   # Playwright-powered controlled browser runtime
│   ├── automation_runtime.py # Durable automation executor and scheduler
│   ├── worker.py            # Durable job worker (lease, SKIP LOCKED)
│   ├── scheduler.py         # Cron schedule compiler and validator
│   ├── repository.py        # Storage abstraction (Supabase + SQLite fallback)
│   ├── supabase_repository.py
│   ├── builtin_skills.py    # Installs skills/ on first owner login
│   ├── capabilities.py      # Typed capability registry
│   ├── production_readiness.py
│   └── ...                  # (all other modules)
├── skills/                  # Built-in Agent Skills
│   ├── class-12-study-planning/SKILL.md
│   ├── automation-health-audit/SKILL.md
│   ├── browser-dom-control/SKILL.md
│   ├── grounded-research/SKILL.md
│   └── youtube-music-memory/SKILL.md
├── tests/                   # pytest test suite (local use; excluded from Docker image)
├── Dockerfile               # Playwright-capable image (mcr.microsoft.com/playwright/python)
├── render.yaml              # Render Blueprint (dockerContext = this folder)
├── requirements.txt         # Pinned Python dependencies
├── .env.example             # Full env var reference
├── env.runtime.example      # Runtime-specific env var guide with comments
├── .dockerignore            # Excludes tests, caches, .db, .env from build
└── README.md                # This file
```

## Why self-contained?

`app/builtin_skills.py` resolves the skills directory as:
```python
SKILLS_ROOT = Path(__file__).resolve().parents[2] / 'skills'
```
That means `skills/` must sit two levels above `app/` inside the image — i.e. at `/app/skills/`. The Dockerfile copies both `app/` and `skills/` into `/app/`, satisfying the path contract without any bind mounts or cross-context copies.

## How to deploy (Render account B)

1. In Render account B → **Blueprints** → **New Blueprint Instance**.
2. Connect your repository. Set **Blueprint file path** to `deploy/render-runtime/render.yaml`.
3. Render builds the image using `deploy/render-runtime/` as the Docker context — fully local, no cross-directory paths.
4. In the service's **Environment** tab, fill in every `sync: false` variable:

### Required env vars

| Variable | Notes |
|----------|-------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Never expose to browser |
| `OWNER_USER_ID` | Heoster's Supabase `auth.users` UUID |
| `CORS_ORIGINS` | Exact Vercel origin, e.g. `https://tillu.vercel.app` |
| `PUBLIC_APP_URL` | Same as CORS_ORIGINS |
| `TILLU_INTERNAL_SECRET` | Must match Brain's `TILLU_INTERNAL_SECRET` |
| `CRON_SECRET` | Protects `/api/internal/*` |
| `BACKUP_ENCRYPTION_KEY` | At-rest backup encryption |
| `VAPID_PUBLIC_KEY` | PWA Web Push (generate with `npx web-push generate-vapid-keys`) |
| `VAPID_PRIVATE_KEY` | PWA Web Push private key |
| `VAPID_SUBJECT` | e.g. `mailto:heoster@example.com` |

See `env.runtime.example` for the full annotated list.

## Local build and run

```bash
# From repo root — context is this folder
docker build -f deploy/render-runtime/Dockerfile deploy/render-runtime -t tillu-runtime

# Run with example env (fill real values first)
docker run --rm -p 8000:8000 --env-file deploy/render-runtime/env.runtime.example tillu-runtime
```

Health check: `curl http://localhost:8000/api/health/live`

> The Playwright/Chromium base image is ~1.5 GB. First pull takes a few minutes.

## Running tests locally

```bash
cd deploy/render-runtime
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
PYTHONPATH=. pytest tests -q
```

## Keeping in sync with apps/api

This folder is a **copy** of `apps/api`. When you update `apps/api/app/`, `skills/`, `requirements.txt`, or tests, re-sync with:

```bash
# From repo root (PowerShell)
Copy-Item -Path apps/api/app    -Destination deploy/render-runtime/app    -Recurse -Force
Copy-Item -Path skills          -Destination deploy/render-runtime/skills  -Recurse -Force
Copy-Item -Path apps/api/requirements.txt -Destination deploy/render-runtime/requirements.txt -Force
Copy-Item -Path apps/api/tests  -Destination deploy/render-runtime/tests   -Recurse -Force
```

For the Brain package, see `deploy/render-brain/`.
