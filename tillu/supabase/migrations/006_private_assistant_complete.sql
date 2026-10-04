-- Complete private-assistant entities required by the current API surface.
create table if not exists public.tasks(
 id text primary key,user_id uuid not null references auth.users on delete cascade,title text not null,subject text,due_at timestamptz,
 status text not null default 'todo' check(status in('todo','doing','done')),priority smallint not null default 2 check(priority between 1 and 3),created_at timestamptz not null default now());
create table if not exists public.calendar_events(
 id text primary key,user_id uuid not null references auth.users on delete cascade,title text not null,subject text,start_at timestamptz not null,end_at timestamptz,
 reminder_minutes int not null default 15,status text not null default 'scheduled',created_at timestamptz not null default now());
create table if not exists public.research_sources(
 id text primary key,user_id uuid not null references auth.users on delete cascade,url text not null,title text not null,content text not null,created_at timestamptz not null default now());
create table if not exists public.browser_history(
 id text primary key,user_id uuid not null references auth.users on delete cascade,url text not null,title text,visited_at timestamptz not null default now());
create table if not exists public.document_chunks(
 id bigint generated always as identity primary key,file_id uuid not null references public.files on delete cascade,user_id uuid not null references auth.users on delete cascade,
 page int not null,section text,content text not null,embedding vector(768),parser_version text not null default 'local-v1',created_at timestamptz not null default now());
create index if not exists document_chunks_file_idx on public.document_chunks(user_id,file_id,page);
create table if not exists public.user_settings(
 user_id uuid primary key references auth.users on delete cascade,settings jsonb not null default '{}',updated_at timestamptz not null default now());
create table if not exists public.action_proposals(
 id text primary key,user_id uuid not null references auth.users on delete cascade,kind text not null,payload jsonb not null,status text not null default 'pending',
 expires_at timestamptz not null,result jsonb,created_at timestamptz not null default now(),decided_at timestamptz);
create index if not exists action_proposals_owner_status_idx on public.action_proposals(user_id,status,expires_at);
create table if not exists public.canvases(
 id text primary key,user_id uuid not null references auth.users on delete cascade,title text not null,data text not null default '',created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create table if not exists public.agent_checkpoints(
 run_id text primary key,user_id uuid not null references auth.users on delete cascade,state jsonb not null,status text not null,updated_at timestamptz not null default now());

alter table public.conversations add column if not exists updated_at timestamptz not null default now();
alter table public.conversations add column if not exists pinned boolean not null default false;
alter table public.conversations add column if not exists archived boolean not null default false;
alter table public.messages add column if not exists metadata jsonb not null default '{}';
alter table public.files add column if not exists size bigint;
alter table public.action_plans add column if not exists run_id text;
alter table public.action_plans add column if not exists data jsonb not null default '{}';

alter table public.tasks enable row level security;alter table public.calendar_events enable row level security;alter table public.research_sources enable row level security;
alter table public.browser_history enable row level security;alter table public.document_chunks enable row level security;alter table public.user_settings enable row level security;
alter table public.action_proposals enable row level security;alter table public.canvases enable row level security;alter table public.agent_checkpoints enable row level security;
create policy "own tasks" on public.tasks for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own calendar" on public.calendar_events for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own research" on public.research_sources for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own browser history" on public.browser_history for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own document chunks" on public.document_chunks for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own settings" on public.user_settings for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own proposals" on public.action_proposals for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own canvases" on public.canvases for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own checkpoints" on public.agent_checkpoints for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
