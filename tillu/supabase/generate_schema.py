"""Regenerate schema.sql from ordered migration files without changing migrations."""
from pathlib import Path

root=Path(__file__).resolve().parent
files=sorted((root/'migrations').glob('*.sql'))
expected=[f'{n:03d}_' for n in range(1,17)]
missing=[prefix for prefix in expected if not any(x.name.startswith(prefix) for x in files)]
if missing:raise SystemExit('Missing migrations: '+', '.join(missing))
header='''-- TILLU unified Supabase schema
-- Built by and for Heoster.
-- Generated from ordered migrations 001-016 for a NEW Supabase project.
-- Do not run this file on a database that already has these migrations applied.
-- Existing projects must continue applying individual files from supabase/migrations.
-- Production source of truth: Supabase Postgres; SQLite is development/test only.

'''
parts=[header]
for file in files:
    parts.extend([f'-- ============================================================================\n-- BEGIN {file.name}\n-- ============================================================================\n\n',file.read_text().rstrip()+'\n\n',f'-- END {file.name}\n\n'])
(root/'schema.sql').write_text(''.join(parts))
print(f'Generated schema.sql from {len(files)} migrations')
