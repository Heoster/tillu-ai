# Configuration

Never commit `.env`, provider keys, Supabase service-role keys, OAuth refresh tokens, WhatsApp tokens or private documents. Copy `apps/api/.env.example` to `apps/api/.env` for local use.

## Required only for hosted production

```env
ENVIRONMENT=production
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
OWNER_USER_ID=
# OWNER_EMAIL= may be used as a secondary owner match
CORS_ORIGINS=https://your-vercel-app.example
PUBLIC_APP_URL=https://your-vercel-app.example
CRON_SECRET=
```

Production startup also requires at least one configured AI provider. `OWNER_USER_ID` is preferred because it is stable. Keep Supabase public signup closed or otherwise ensure every non-owner identity is rejected by the API.

## AI providers

All are optional individually; configure one or more:

```env
GROQ_API_KEY=
CEREBRAS_API_KEY=
GOOGLE_API_KEY=
OPENROUTER_API_KEY=
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
```

The gateway assigns providers to intent, planning and execution phases according to capability, cost, RPM/TPM headroom, latency and health. Model names are configurable with `GROQ_MODEL`, `CEREBRAS_MODEL`, `GOOGLE_MODEL`, `OPENROUTER_MODEL` and `CLOUDFLARE_MODEL`.

## Search and source providers

```env
PARALLEL_API_KEY=
YOU_API_KEY=
TAVILY_API_KEY=
FIRECRAWL_API_KEY=
SEARCH_PROVIDER_ORDER=parallel,you,tavily,firecrawl,wikipedia
```

Open-Meteo, GDELT, Hacker News and Wikipedia provide keyless paths. Availability, quotas and terms can change; adapters must report failures rather than simulate results.

## Optional communications

These variables may remain blank. TILLU continues to work and the UI reports the integration as disabled.

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=
```

Gmail currently supports search/read and approval-gated draft foundations. WhatsApp uses the official Cloud API and normally requires a Business number. Personal WhatsApp Web automation is intentionally not used.

## Browser and local behavior

```env
BROWSER_HEADLESS=true
DEFAULT_LATITUDE=29.97
DEFAULT_LONGITUDE=77.55
RATE_LIMIT_PER_MINUTE=120
LOG_LEVEL=INFO
```

The Docker image includes Playwright Chromium. Browser interactions occur in isolated sessions; navigate/read are immediate and click/type are approval-gated.

## Frontend

```env
VITE_API_URL=/api
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

Use relative `/api` through the Vite/Vercel proxy where possible. Never expose service-role, model, search, Gmail or WhatsApp secrets to browser code.

## Current limitation

Supabase configuration does not yet mean every route uses Postgres. SQLite remains the primary repository for several core resources; see `FEATURE_STATUS.md` and `ARCHITECTURE_AUDIT.md`.
