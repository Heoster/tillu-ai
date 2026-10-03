# Getting started

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- Git
- Docker recommended for the full Playwright browser runtime

## API

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

Expected version is currently `0.4.0`; optional integrations may show `disabled`.

## PWA

```bash
cd apps/web
npm install
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173`. Vite proxies `/api` to the local API.

## Development identity

Without Supabase configuration, non-production mode uses the explicit local Heoster identity and SQLite. Production refuses missing Supabase/owner/model/CORS configuration. Development fallback is not a production authentication mode.

## First checks

1. Open Assistant and ask `calculate 72/8+3`.
2. Confirm the response shows Intent, Planning and Execution phases plus a calculation widget.
3. Ask for current weather and confirm the weather tool/widget and source.
4. Enter `create task: Review current electricity`; verify an approval appears and no task exists before approval.
5. Open Integrations and confirm missing Gmail/WhatsApp credentials are reported as disabled.
6. Run `GET /api/providers` to inspect configured models and router health.

## Controlled browser

The recommended route is Docker because the Playwright base image contains Chromium dependencies:

```bash
docker build -t tillu-api apps/api
docker run --rm -p 8000:8000 --env-file apps/api/.env tillu-api
```

For native Linux development, run `playwright install chromium` and install Playwright host dependencies.

## Verification

```bash
cd apps/api
PYTHONPATH=. pytest tests -q
python -m compileall app

cd ../web
npm run build
```

The current five tests are only a baseline; security, tenancy/owner, queue, provider-fallback, browser and end-to-end coverage remains required.
