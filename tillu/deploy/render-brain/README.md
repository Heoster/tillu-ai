# deploy/render-brain — TILLU Brain (Render account A)

This folder is a **fully self-contained** deployment package for the Brain service. It contains everything the Docker build needs — no files are resolved from `apps/api` or anywhere else in the repository at build time.

## Folder structure

```
deploy/render-brain/
├── app/                     # Full FastAPI application source (copied from apps/api/app/)
│   ├── main.py              # FastAPI entry point, all routes
│   ├── config.py            # Settings (pydantic-settings, reads from env)
│   ├── auth.py              # Supabase JWT auth
│   ├── orchestrator.py      # LangGraph orchestration loop
│   ├── planner.py           # Plan compiler
│   ├── providers.py         # Multi-provider AI gateway (Groq, Cerebras, Google, OpenRouter, Cloudflare)
│   ├── model_library.py     # Model catalogue and routing
│   ├── honcho_adapter.py    # Honcho long-term memory integration
│   ├── repository.py        # Storage abstraction (Supabase + SQLite fallback)
│   ├── supabase_repository.py
│   ├── learning.py          # Skill parsing, session analysis, memory recall
│   ├── builtin_skills.py    # Installs skills/ on first owner login
│   ├── capabilities.py      # Typed capability registry
│   ├── pipeline.py          # RPC pipeline execution
│   ├── delegation.py        # Sub-agent delegation
│   ├── production_readiness.py
│   └── ...                  # (all other modules)
├── skills/                  # Built-in Agent Skills
│   ├── class-12-study-planning/SKILL.md
│   ├── automation-health-audit/SKILL.md
│   ├── browser-dom-control/SKILL.md
│   ├── grounded-research/SKILL.md
│   └── youtube-music-memory/SKILL.md
├── tests/                   # pytest test suite (local use; excluded from Docker image)
├── Dockerfile.brain         # Slim python:3.13-slim image, no Playwright
├── render.yaml              # Render Blueprint (dockerContext = this folder)
├── requirements.txt         # Pinned Python dependencies
├── .env.example             # Full env var reference
├── env.brain.example        # Brain-specific env var guide with comments
├── .dockerignore            # Excludes tests, caches, .db, .env from build
└── README.md                # This file
```

## Why self-contained?

`app/builtin_skills.py` resolves the skills directory as:
```python
SKILLS_ROOT = Path(__file__).resolve().parents[2] / 'skills'
```
That means `skills/` must sit two levels above `app/` inside the image — i.e. at `/app/skills/`. The Dockerfile copies both `app/` and `skills/` into `/app/`, satisfying the path contract without any bind mounts or cross-context copies.

## How to deploy (Render account A)

1. In Render account A → **Blueprints** → **New Blueprint Instance**.
2. Connect your repository. Set **Blueprint file path** to `deploy/render-brain/render.yaml`.
3. Render builds the image using `deploy/render-brain/` as the Docker context — fully local, no cross-directory paths.
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
| `RUNTIME_INTERNAL_URL` | Internal URL of the Runtime service (account B) |
| `TILLU_INTERNAL_SECRET` | Shared secret with Runtime — `openssl rand -hex 32` |
| `CRON_SECRET` | Protects `/api/internal/*` |
| `RPC_CAPABILITY_SECRET` | Protects inter-service RPC |
| `BACKUP_ENCRYPTION_KEY` | At-rest backup encryption |
| `HONCHO_API_KEY` | Honcho long-term memory key |
| At least one of: `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` | AI model provider |

See `env.brain.example` for the full annotated list.

## Local build and run

```bash
# From repo root — context is this folder
docker build -f deploy/render-brain/Dockerfile.brain deploy/render-brain -t tillu-brain

# Run with example env (fill real values first)
docker run --rm -p 8000:8000 --env-file deploy/render-brain/env.brain.example tillu-brain
```

Health check: `curl http://localhost:8000/api/health/live`

## Running tests locally

```bash
cd deploy/render-brain
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
PYTHONPATH=. pytest tests -q
```

## Keeping in sync with apps/api

This folder is a **copy** of `apps/api`. When you update `apps/api/app/`, `skills/`, `requirements.txt`, or tests, re-sync with:

```bash
# From repo root (PowerShell)
Copy-Item -Path apps/api/app    -Destination deploy/render-brain/app    -Recurse -Force
Copy-Item -Path skills          -Destination deploy/render-brain/skills  -Recurse -Force
Copy-Item -Path apps/api/requirements.txt -Destination deploy/render-brain/requirements.txt -Force
Copy-Item -Path apps/api/tests  -Destination deploy/render-brain/tests   -Recurse -Force
```

For the Runtime package, see `deploy/render-runtime/`.
