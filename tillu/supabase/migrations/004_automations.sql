create table if not exists public.automations(
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users on delete cascade,
 name text not null, trigger_type text not null check(trigger_type in ('schedule','manual','event')),
 schedule text, action_type text not null, config jsonb not null default '{}', enabled boolean not null default true,
 last_run_at timestamptz, next_run_at timestamptz, created_at timestamptz not null default now()
);
alter table public.automations enable row level security;
create policy "own automations" on public.automations for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create index if not exists automations_due_idx on public.automations(enabled,next_run_at);
create table if not exists public.automation_runs(
 id uuid primary key default gen_random_uuid(), automation_id uuid not null references public.automations on delete cascade,
 user_id uuid not null references auth.users on delete cascade, status text not null, output text, error text,
 started_at timestamptz not null default now(), completed_at timestamptz
);
alter table public.automation_runs enable row level security;
create policy "own automation runs" on public.automation_runs for select using(auth.uid()=user_id);
