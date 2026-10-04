create table if not exists public.notes(
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  title text not null default 'Untitled note',
  content text not null default '',
  canvas_data jsonb,
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.notes enable row level security;
create policy "own notes" on public.notes for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create index if not exists notes_user_updated_idx on public.notes(user_id,updated_at desc);
do $$ begin alter publication supabase_realtime add table public.notes; exception when duplicate_object then null; end $$;
