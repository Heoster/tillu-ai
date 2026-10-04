-- Bounded, isolated read-only delegate execution records.
create table if not exists public.delegate_runs(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,
 parent_run_id uuid,objective text not null,status text not null check(status in('planning','running','completed','failed','cancelled')),
 plan jsonb not null default '{}',result jsonb,error text,created_at timestamptz not null default now(),completed_at timestamptz
);
create table if not exists public.delegate_workstreams(
 id uuid primary key default gen_random_uuid(),run_id uuid not null references public.delegate_runs on delete cascade,user_id uuid not null references auth.users on delete cascade,
 ordinal int not null,name text not null,objective text not null,status text not null check(status in('pending','running','completed','failed','cancelled')),
 tool_calls jsonb not null default '[]',result jsonb,error text,started_at timestamptz,completed_at timestamptz,unique(run_id,ordinal)
);
alter table public.delegate_runs enable row level security;alter table public.delegate_workstreams enable row level security;
create policy "own delegate runs" on public.delegate_runs for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own delegate workstreams" on public.delegate_workstreams for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create index if not exists delegate_runs_owner_idx on public.delegate_runs(user_id,created_at desc);
