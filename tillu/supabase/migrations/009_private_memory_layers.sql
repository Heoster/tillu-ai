-- Explicit, owner-controlled layered memory for TILLU.
create table if not exists public.memories(
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users on delete cascade,
 layer text not null check(layer in('identity','people','preferences','projects','routines','episodic')),
 key text not null,
 value jsonb not null,
 sensitivity text not null default 'private' check(sensitivity in('private','sensitive')),
 source text not null default 'explicit_chat',
 confidence real not null default 1 check(confidence between 0 and 1),
 status text not null default 'active' check(status in('active','archived')),
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),last_used_at timestamptz,
 unique(user_id,layer,key)
);
create index if not exists memories_owner_layer_idx on public.memories(user_id,layer,status,updated_at desc);
alter table public.memories enable row level security;
create policy "own memories" on public.memories for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
