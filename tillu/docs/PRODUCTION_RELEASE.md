# TILLU production release verification

TILLU is built by and for Heoster. This checklist distinguishes code readiness, configuration, and live verification.

## Required configuration

Set `ENVIRONMENT=production`, owner UUID/email, Supabase URL/service key, restricted HTTPS CORS/app URLs, at least one hosted model provider, and independent random values for `CRON_SECRET`, `RPC_CAPABILITY_SECRET`, and `BACKUP_ENCRYPTION_KEY`.

Optional channels remain fail-closed until configured: VAPID Web Push, Gmail OAuth, WhatsApp Cloud API, search providers, and Honcho.

## Database

For a completely new project, run `supabase/schema.sql` once. For an existing project, apply migrations `001` through `016` incrementally in order and never rerun the unified snapshot. Migration `015` adds durable idempotency receipts for consequential Brain-to-Runtime RPC effects. Migrations `008`–`014` contain important atomic claims, memory, briefings, learning, durable scheduling, delegates, and RPC pipelines.

After applying them:

1. Start the API with production settings. Startup must complete its required-schema probe.
2. Sign in as Heoster through Supabase Auth.
3. Verify owner rows are readable with Heoster's JWT.
4. Verify an anonymous token and a different authenticated user cannot read or mutate owner rows.
5. Verify service-role credentials are present only on the backend.

## API diagnostics

Authenticated endpoint: `GET /api/production-readiness`.

`ready=true` means required configuration is present, not that external delivery has been proven. The response deliberately reports live checks as `not_tested` until they are exercised.

## Live checks

- Create, pause, resume, claim, retry, cancel, and recover an automation under concurrent workers.
- Invoke protected cron endpoints with the correct and incorrect secret.
- Subscribe from the production HTTPS origin and send a Web Push test.
- Test Gmail and WhatsApp using recipient-specific approval proposals.
- Create and restore a test encrypted backup. Never log the plaintext or encryption key.
- Run cross-session recall and verify every cited message belongs to Heoster.
- Activate a test skill and verify unapproved revisions remain drafts.
- Execute parallel delegates and verify attempted action tools are filtered.
- Run a declarative pipeline and the restricted Python-syntax RPC runner; confirm action calls pause for approval.

## Release gate

Do not call the deployment production-verified until:

- `/api/production-readiness` has no required blockers.
- RLS isolation has been tested with real JWTs.
- Cron and restart recovery have been exercised on the hosting platform.
- Each advertised delivery channel has one successful audited delivery.
- Backup restoration—not only backup creation—has been tested.
- Backend tests and frontend production build pass from a clean checkout.
