# Frontend hosting entry

This directory documents the hosting entry for the real UI in `apps/web`; it contains no copied or placeholder UI.

## Vercel deployment (recommended)

1. Import the repository into Vercel.
2. Set **Root Directory** to `apps/web`.
3. Vercel reads `apps/web/vercel.json` — this configures the Vite build, SPA routing rewrites, and security headers.
4. Set the following environment variables in the Vercel dashboard:

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | HTTPS URL of the Brain Render service, ending in `/api` (e.g. `https://tillu-brain.onrender.com/api`) |
| `VITE_SUPABASE_URL` | Your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Your Supabase anon/public key (browser-safe) |

Never put backend service-role keys or AI provider secrets in Vercel or the browser bundle.

5. Copy public values from `apps/web/.env.production.example` as a reference.

## Security headers (vercel.json)

The following headers are applied to all routes via `apps/web/vercel.json`:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

## Post-deploy step

After Vercel assigns a domain, add the exact Vercel origin to the Brain Render service's `CORS_ORIGINS` environment variable. Example:

```
CORS_ORIGINS=https://tillu.vercel.app,https://your-custom-domain.com
```

Restart the Brain service after updating `CORS_ORIGINS`.

## Docker self-host (alternative)

To self-host the frontend without Vercel, use `apps/web/Dockerfile` + `apps/web/nginx.conf`:

```bash
# Build the image (pass env vars as build args)
docker build \
  --build-arg VITE_API_URL=https://your-brain-api.example.com/api \
  --build-arg VITE_SUPABASE_URL=https://your-project.supabase.co \
  --build-arg VITE_SUPABASE_ANON_KEY=your-anon-key \
  -t tillu-web apps/web

# Run on port 8080
docker run --rm -p 8080:8080 tillu-web
```

The nginx config (`apps/web/nginx.conf`) serves the SPA with the same security headers and handles `/assets/` with immutable caching.

## Local verification

```bash
npm --prefix apps/web ci
npm --prefix apps/web run build
```
