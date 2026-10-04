# TILLU Supabase schema

TILLU uses Supabase Postgres as its production source of truth.

## New project: one-file installation

For a completely new Supabase project, open the SQL Editor and run:

- `schema.sql`

This unified file contains migrations `001` through `016` in their required order, including tables, indexes, functions, storage buckets, constraints, RLS, policies, queues, memory, learning, schedules, delegates, pipelines, and internal RPC receipts.

Run it once only on a new project.

## Existing project: incremental migrations

Do **not** run `schema.sql` on a project where some TILLU migrations are already installed. Apply only the missing files from `migrations/` in numerical order.

The individual migration files remain canonical for upgrades and deployment history. `schema.sql` is the canonical fresh-install snapshot generated from them.

## Regeneration

After adding a migration, update the expected migration range in `generate_schema.py`, then run:

```bash
python supabase/generate_schema.py
```

Review the resulting diff and run database tests before release.

## Security

- Never place `SUPABASE_SERVICE_ROLE_KEY` in Vercel or browser code.
- Keep Brain and Runtime service-role credentials only in their server environments.
- Test RLS with Heoster's JWT, an anonymous client, and a different authenticated user.
- Storage buckets are private unless a migration explicitly states otherwise.
- Applying SQL successfully does not by itself prove RLS or integration correctness.
