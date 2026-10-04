-- TILLU unified Supabase schema
-- Built by and for Heoster.
-- Generated from ordered migrations 001-016 for a NEW Supabase project.
-- Do not run this file on a database that already has these migrations applied.
-- Existing projects must continue applying individual files from supabase/migrations.
-- Production source of truth: Supabase Postgres; SQLite is development/test only.

-- ============================================================================
-- BEGIN 001_tillu_core.sql
-- ============================================================================

create extension if not exists vector;
create type public.risk_level as enum ('read','write','external','sensitive');
create type public.job_status as enum ('queued','running','completed','failed','cancelled');
create table public.profiles(id uuid primary key references auth.users on delete cascade, display_name text, class_level text default '12', board text default 'CBSE', created_at timestamptz default now());
create table public.subjects(id uuid primary key default gen_random_uuid(), code text unique not null, name text not null, color text);
create table public.chapters(id uuid primary key default gen_random_uuid(), subject_id uuid references public.subjects on delete cascade, title text not null, position int not null, unique(subject_id,position));
create table public.topics(id uuid primary key default gen_random_uuid(), chapter_id uuid references public.chapters on delete cascade, title text not null, position int not null);
create table public.topic_progress(user_id uuid references auth.users on delete cascade, topic_id uuid references public.topics on delete cascade, status text default 'not_started', confidence smallint default 0 check(confidence between 0 and 100), updated_at timestamptz default now(), primary key(user_id,topic_id));
create table public.conversations(id uuid primary key default gen_random_uuid(), user_id uuid references auth.users on delete cascade, title text, created_at timestamptz default now());
create table public.messages(id uuid primary key default gen_random_uuid(), conversation_id uuid references public.conversations on delete cascade, role text not null check(role in('user','assistant','tool')), content jsonb not null, created_at timestamptz default now());
create table public.action_plans(id uuid primary key default gen_random_uuid(), user_id uuid references auth.users on delete cascade, title text not null, summary text, steps jsonb not null default '[]', risk public.risk_level not null, status text default 'proposed', created_at timestamptz default now());
create table public.jobs(id uuid primary key default gen_random_uuid(), user_id uuid references auth.users on delete cascade, kind text not null, status public.job_status default 'queued', payload jsonb default '{}', result jsonb, progress smallint default 0, lease_until timestamptz, attempts int default 0, created_at timestamptz default now(), updated_at timestamptz default now());
create table public.files(id uuid primary key default gen_random_uuid(), user_id uuid references auth.users on delete cascade, storage_path text not null, name text not null, mime_type text, sha256 text, source_url text, metadata jsonb default '{}', created_at timestamptz default now());
create table public.audit_events(id bigint generated always as identity primary key, user_id uuid references auth.users on delete cascade, action text not null, risk public.risk_level not null, input_redacted jsonb, result_redacted jsonb, created_at timestamptz default now());
alter table public.profiles enable row level security; alter table public.topic_progress enable row level security; alter table public.conversations enable row level security; alter table public.messages enable row level security; alter table public.action_plans enable row level security; alter table public.jobs enable row level security; alter table public.files enable row level security; alter table public.audit_events enable row level security;
create policy "own profile" on public.profiles for all using(auth.uid()=id) with check(auth.uid()=id);
create policy "own progress" on public.topic_progress for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own conversations" on public.conversations for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own plans" on public.action_plans for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own jobs" on public.jobs for select using(auth.uid()=user_id);
create policy "own files" on public.files for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own audit" on public.audit_events for select using(auth.uid()=user_id);
create policy "conversation messages" on public.messages for all using(exists(select 1 from public.conversations c where c.id=conversation_id and c.user_id=auth.uid())) with check(exists(select 1 from public.conversations c where c.id=conversation_id and c.user_id=auth.uid()));

-- END 001_tillu_core.sql

-- ============================================================================
-- BEGIN 002_storage_sync.sql
-- ============================================================================

-- TILLU private document storage and device synchronization
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('documents','documents',false,26214400,array['application/pdf'])
on conflict(id) do update set public=false,file_size_limit=26214400;

create policy "users upload own documents" on storage.objects for insert to authenticated
with check(bucket_id='documents' and (storage.foldername(name))[1]=auth.uid()::text);
create policy "users read own documents" on storage.objects for select to authenticated
using(bucket_id='documents' and (storage.foldername(name))[1]=auth.uid()::text);
create policy "users delete own documents" on storage.objects for delete to authenticated
using(bucket_id='documents' and (storage.foldername(name))[1]=auth.uid()::text);

create table if not exists public.devices(
  id text not null,
  user_id uuid not null references auth.users on delete cascade,
  name text,
  platform text,
  last_seen_at timestamptz default now(),
  created_at timestamptz default now(),
  primary key(user_id,id)
);
alter table public.devices enable row level security;
create policy "own devices" on public.devices for all using(auth.uid()=user_id) with check(auth.uid()=user_id);

alter table public.topic_progress add column if not exists version bigint not null default 1;
alter table public.topic_progress add column if not exists device_id text;
create index if not exists jobs_user_status_idx on public.jobs(user_id,status,created_at desc);
create index if not exists files_user_sha_idx on public.files(user_id,sha256);

-- Realtime publication may already contain these tables.
do $$ begin
  alter publication supabase_realtime add table public.topic_progress;
exception when duplicate_object then null;
end $$;
do $$ begin
  alter publication supabase_realtime add table public.jobs;
exception when duplicate_object then null;
end $$;

-- END 002_storage_sync.sql

-- ============================================================================
-- BEGIN 003_notes_workspace.sql
-- ============================================================================

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

-- END 003_notes_workspace.sql

-- ============================================================================
-- BEGIN 004_automations.sql
-- ============================================================================

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

-- END 004_automations.sql

-- ============================================================================
-- BEGIN 005_execution_hardening.sql
-- ============================================================================

-- Durable execution, automation locking, and quota governance.
alter table public.jobs add column if not exists idempotency_key text;
alter table public.jobs add column if not exists available_at timestamptz not null default now();
alter table public.jobs add column if not exists leased_by text;
alter table public.jobs add column if not exists last_error text;
alter table public.jobs add column if not exists max_attempts int not null default 5;
create unique index if not exists jobs_user_idempotency_idx on public.jobs(user_id,idempotency_key) where idempotency_key is not null;
create index if not exists jobs_claim_idx on public.jobs(status,available_at,lease_until);

create or replace function public.claim_jobs(worker text, batch_size int default 5, lease_seconds int default 120)
returns setof public.jobs language plpgsql security definer set search_path=public as $$
begin
 return query
 with candidates as (
  select id from public.jobs
  where status='queued' and available_at<=now() and (lease_until is null or lease_until<now()) and attempts<max_attempts
  order by created_at for update skip locked limit greatest(1,least(batch_size,20))
 ), claimed as (
  update public.jobs j set status='running',leased_by=worker,lease_until=now()+make_interval(secs=>lease_seconds),attempts=attempts+1,updated_at=now()
  from candidates c where j.id=c.id returning j.*
 ) select * from claimed;
end $$;
revoke all on function public.claim_jobs(text,int,int) from public,anon,authenticated;
grant execute on function public.claim_jobs(text,int,int) to service_role;

create table if not exists public.automation_occurrences(
 id uuid primary key default gen_random_uuid(), automation_id uuid not null references public.automations on delete cascade,
 user_id uuid not null references auth.users on delete cascade, scheduled_for timestamptz not null,
 status text not null default 'queued', job_id uuid references public.jobs on delete set null, created_at timestamptz not null default now(),
 unique(automation_id,scheduled_for)
);
alter table public.automation_occurrences enable row level security;
create policy "own automation occurrences" on public.automation_occurrences for select using(auth.uid()=user_id);

create or replace function public.enqueue_due_automations(batch_size int default 50)
returns int language plpgsql security definer set search_path=public as $$
declare inserted_count int;
begin
 with due as (
  select * from public.automations where enabled=true and next_run_at<=now()
  order by next_run_at for update skip locked limit greatest(1,least(batch_size,100))
 ), occurrences as (
  insert into public.automation_occurrences(automation_id,user_id,scheduled_for)
  select id,user_id,next_run_at from due on conflict(automation_id,scheduled_for) do nothing returning *
 ), jobs_inserted as (
  insert into public.jobs(user_id,kind,payload,idempotency_key)
  select user_id,'automation_run',jsonb_build_object('automation_id',automation_id,'scheduled_for',scheduled_for),
         'automation:'||automation_id::text||':'||scheduled_for::text from occurrences returning id,idempotency_key
 ) select count(*) into inserted_count from jobs_inserted;
 return inserted_count;
end $$;
revoke all on function public.enqueue_due_automations(int) from public,anon,authenticated;
grant execute on function public.enqueue_due_automations(int) to service_role;

create table if not exists public.usage_ledger(
 id bigint generated always as identity primary key,user_id uuid references auth.users on delete cascade,
 provider text not null,operation text not null,units bigint not null default 1,cost_microusd bigint not null default 0,
 request_id text,created_at timestamptz not null default now()
);
alter table public.usage_ledger enable row level security;
create policy "own usage" on public.usage_ledger for select using(auth.uid()=user_id);
create index if not exists usage_user_day_idx on public.usage_ledger(user_id,created_at desc);

create table if not exists public.usage_limits(
 user_id uuid primary key references auth.users on delete cascade,daily_model_requests int not null default 200,
 daily_search_requests int not null default 100,daily_tool_requests int not null default 500,monthly_cost_microusd bigint not null default 5000000
);
alter table public.usage_limits enable row level security;
create policy "own usage limits" on public.usage_limits for select using(auth.uid()=user_id);

create or replace function public.consume_quota(uid uuid,provider_name text,operation_name text,unit_count bigint default 1,req_id text default null)
returns boolean language plpgsql security definer set search_path=public as $$
declare used_count bigint;allowed_count bigint;
begin
 if auth.role()<>'service_role' then raise exception 'service role required'; end if;
 select case when operation_name='search' then daily_search_requests when operation_name='model' then daily_model_requests else daily_tool_requests end
 into allowed_count from public.usage_limits where user_id=uid;
 allowed_count:=coalesce(allowed_count,case when operation_name='search' then 100 when operation_name='model' then 200 else 500 end);
 select coalesce(sum(units),0) into used_count from public.usage_ledger where user_id=uid and operation=operation_name and created_at>=date_trunc('day',now());
 if used_count+unit_count>allowed_count then return false; end if;
 insert into public.usage_ledger(user_id,provider,operation,units,request_id) values(uid,provider_name,operation_name,unit_count,req_id);
 return true;
end $$;
revoke all on function public.consume_quota(uuid,text,text,bigint,text) from public,anon,authenticated;
grant execute on function public.consume_quota(uuid,text,text,bigint,text) to service_role;

-- END 005_execution_hardening.sql

-- ============================================================================
-- BEGIN 006_private_assistant_complete.sql
-- ============================================================================

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

-- END 006_private_assistant_complete.sql

-- ============================================================================
-- BEGIN 007_production_repository.sql
-- ============================================================================

-- Production repository support and atomic approval claims.
-- Keeps the static syllabus's stable string topic IDs separate from curriculum UUIDs.
create table if not exists public.assistant_topic_progress(
 user_id uuid not null references auth.users on delete cascade,
 topic_id text not null,
 status text not null default 'not_started' check(status in('not_started','learning','practiced','mastered','revision_due')),
 confidence smallint not null default 0 check(confidence between 0 and 100),
 updated_at timestamptz not null default now(),
 primary key(user_id,topic_id)
);
create table if not exists public.service_cache(
 key text primary key,value jsonb not null,updated_at timestamptz not null default now()
);
alter table public.assistant_topic_progress enable row level security;
create policy "own assistant progress" on public.assistant_topic_progress for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
-- Cached public feed data is backend-maintained and authenticated users may read it.
alter table public.service_cache enable row level security;
create policy "authenticated cache read" on public.service_cache for select to authenticated using(true);

create or replace function public.claim_action_proposal(proposal_id text,uid uuid)
returns boolean language plpgsql security definer set search_path=public as $$
declare changed integer;
begin
 update public.action_proposals
 set status='executing',decided_at=now()
 where id=proposal_id and user_id=uid and status='pending' and expires_at>now();
 get diagnostics changed=row_count;
 return changed=1;
end $$;
revoke all on function public.claim_action_proposal(text,uuid) from public;
grant execute on function public.claim_action_proposal(text,uuid) to service_role;

create or replace function public.due_calendar_reminders(uid uuid,at_time timestamptz)
returns setof public.calendar_events language sql stable security definer set search_path=public as $$
 select * from public.calendar_events
 where user_id=uid and status='scheduled'
 and start_at-(reminder_minutes * interval '1 minute')<=at_time and start_at>=at_time
 order by start_at;
$$;
revoke all on function public.due_calendar_reminders(uuid,timestamptz) from public;
grant execute on function public.due_calendar_reminders(uuid,timestamptz) to service_role;

-- END 007_production_repository.sql

-- ============================================================================
-- BEGIN 008_general_plan_execution.sql
-- ============================================================================

-- Atomic claim for an approved multi-capability plan.
create or replace function public.claim_action_plan(plan_id uuid,uid uuid)
returns boolean language plpgsql security definer set search_path=public as $$
declare changed integer;
begin
 update public.action_plans set status='running'
 where id=plan_id and user_id=uid and status in('proposed','waiting_approval');
 get diagnostics changed=row_count;
 return changed=1;
end $$;
revoke all on function public.claim_action_plan(uuid,uuid) from public;
grant execute on function public.claim_action_plan(uuid,uuid) to service_role;

-- END 008_general_plan_execution.sql

-- ============================================================================
-- BEGIN 009_private_memory_layers.sql
-- ============================================================================

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

-- END 009_private_memory_layers.sql

-- ============================================================================
-- BEGIN 010_proactive_briefings.sql
-- ============================================================================

-- Durable proactive briefings, notification inbox, delivery attempts and push subscriptions.
create table if not exists public.briefing_schedules(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,
 name text not null,kind text not null check(kind in('morning_plan','evening_review','urgent_alerts','study_review','failed_runs')),
 schedule text not null,timezone text not null default 'Asia/Kolkata',channels jsonb not null default '["in_app"]',config jsonb not null default '{}',
 enabled boolean not null default true,next_run_at timestamptz,last_run_at timestamptz,created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create index if not exists briefing_due_idx on public.briefing_schedules(enabled,next_run_at);
create table if not exists public.notifications(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,briefing_id uuid references public.briefing_schedules on delete set null,
 kind text not null,title text not null,body text not null,data jsonb not null default '{}',priority text not null default 'normal' check(priority in('low','normal','high','urgent')),
 status text not null default 'unread' check(status in('unread','read','archived')),created_at timestamptz not null default now(),read_at timestamptz);
create index if not exists notifications_owner_status_idx on public.notifications(user_id,status,created_at desc);
create table if not exists public.delivery_attempts(
 id uuid primary key default gen_random_uuid(),notification_id uuid not null references public.notifications on delete cascade,user_id uuid not null references auth.users on delete cascade,
 channel text not null,status text not null check(status in('queued','delivered','proposal_required','failed','disabled')),
 attempt int not null default 1,error text,external_id text,created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
 unique(notification_id,channel,attempt));
create table if not exists public.push_subscriptions(
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,endpoint text not null,subscription jsonb not null,
 enabled boolean not null default true,created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(user_id,endpoint));

alter table public.briefing_schedules enable row level security;alter table public.notifications enable row level security;
alter table public.delivery_attempts enable row level security;alter table public.push_subscriptions enable row level security;
create policy "own briefing schedules" on public.briefing_schedules for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own notifications" on public.notifications for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own delivery attempts" on public.delivery_attempts for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own push subscriptions" on public.push_subscriptions for all using(auth.uid()=user_id) with check(auth.uid()=user_id);

-- END 010_proactive_briefings.sql

-- ============================================================================
-- BEGIN 011_learning_loop_skills.sql
-- ============================================================================

-- Closed learning loop: summaries, user-model conclusions, nudges and Agent Skills drafts.
create table if not exists public.session_summaries(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,conversation_id uuid not null references public.conversations on delete cascade,summary text not null,topics text[] not null default '{}',message_count int not null default 0,created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(user_id,conversation_id));
create table if not exists public.user_model_conclusions(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,subject text not null,predicate text not null,value jsonb not null,evidence jsonb not null default '[]',confidence real not null check(confidence between 0 and 1),status text not null default 'proposed' check(status in('proposed','accepted','rejected','superseded')),created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create table if not exists public.nudges(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,kind text not null,title text not null,body text not null,evidence jsonb not null default '{}',status text not null default 'pending' check(status in('pending','shown','accepted','dismissed')),due_at timestamptz,created_at timestamptz not null default now());
create table if not exists public.skills(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,name text not null,description text not null,instructions text not null,allowed_capabilities text[] not null default '{}',version int not null default 1,status text not null default 'draft' check(status in('draft','active','archived')),source_plan_id uuid references public.action_plans on delete set null,parent_skill_id uuid references public.skills on delete set null,package_manifest jsonb not null default '{}',metrics jsonb not null default '{}',created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(user_id,name,version));
create table if not exists public.learning_observations(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,conversation_id uuid references public.conversations on delete cascade,kind text not null,content text not null,evidence jsonb not null default '[]',created_at timestamptz not null default now());
create table if not exists public.skill_outcomes(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,skill_id uuid not null references public.skills on delete cascade,run_id uuid,success boolean not null,score real check(score between 0 and 1),evidence jsonb not null default '{}',created_at timestamptz not null default now());
create index if not exists messages_fts_idx on public.messages using gin(to_tsvector('english',coalesce(content::text,'')));
create index if not exists summaries_fts_idx on public.session_summaries using gin(to_tsvector('english',summary));
create or replace function public.search_session_messages(uid uuid,query text,result_limit int default 20) returns table(conversation_id uuid,role text,content text,created_at timestamptz,score real,source text) language sql stable security invoker set search_path=public as $$
 select x.conversation_id,x.role,x.content,x.created_at,x.score,x.source from (
  select m.conversation_id,m.role,m.content::text content,m.created_at,ts_rank(to_tsvector('english',coalesce(m.content::text,'')),websearch_to_tsquery('english',query))::real score,'message'::text source from public.messages m join public.conversations c on c.id=m.conversation_id where c.user_id=uid and to_tsvector('english',coalesce(m.content::text,'')) @@ websearch_to_tsquery('english',query)
  union all
  select s.conversation_id,'summary'::text,s.summary,s.updated_at,ts_rank(to_tsvector('english',s.summary),websearch_to_tsquery('english',query))::real,'summary'::text from public.session_summaries s where s.user_id=uid and to_tsvector('english',s.summary) @@ websearch_to_tsquery('english',query)
 ) x order by x.score desc limit greatest(1,least(result_limit,100)) $$;

alter table public.session_summaries enable row level security;alter table public.user_model_conclusions enable row level security;alter table public.nudges enable row level security;alter table public.skills enable row level security;alter table public.learning_observations enable row level security;alter table public.skill_outcomes enable row level security;
create policy "own summaries" on public.session_summaries for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own conclusions" on public.user_model_conclusions for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own nudges" on public.nudges for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own skills" on public.skills for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own observations" on public.learning_observations for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "own skill outcomes" on public.skill_outcomes for all using(auth.uid()=user_id) with check(auth.uid()=user_id);

-- END 011_learning_loop_skills.sql

-- ============================================================================
-- BEGIN 012_durable_automation_scheduler.sql
-- ============================================================================

-- Durable, timezone-aware automation scheduling and atomic run leases.
alter table public.automations add column if not exists timezone text not null default 'Asia/Kolkata';
alter table public.automations add column if not exists retry_policy jsonb not null default '{"max_attempts":3,"base_delay_seconds":60}';
alter table public.automations add column if not exists updated_at timestamptz not null default now();
alter table public.automation_runs add column if not exists scheduled_for timestamptz;
alter table public.automation_runs add column if not exists idempotency_key text;
alter table public.automation_runs add column if not exists attempt int not null default 1;
alter table public.automation_runs add column if not exists lease_owner text;
alter table public.automation_runs add column if not exists lease_expires_at timestamptz;
alter table public.automation_runs add column if not exists next_attempt_at timestamptz;
alter table public.automation_runs add column if not exists cancelled_at timestamptz;
create unique index if not exists automation_runs_idempotency_idx on public.automation_runs(user_id,idempotency_key) where idempotency_key is not null;
create index if not exists automation_runs_retry_idx on public.automation_runs(status,next_attempt_at,lease_expires_at);

create or replace function public.claim_due_automations(worker text, batch_size int default 25, lease_seconds int default 300)
returns setof public.automation_runs language plpgsql security definer set search_path=public as $$
declare a public.automations; r public.automation_runs; key text;
begin
 for a in select * from public.automations where enabled and next_run_at<=now() order by next_run_at for update skip locked limit greatest(1,least(batch_size,100)) loop
  key:=a.id::text||':'||a.next_run_at::text;
  insert into public.automation_runs(automation_id,user_id,status,scheduled_for,idempotency_key,attempt,lease_owner,lease_expires_at,started_at)
  values(a.id,a.user_id,'claimed',a.next_run_at,key,1,worker,now()+make_interval(secs=>greatest(30,least(lease_seconds,3600))),now())
  on conflict(user_id,idempotency_key) where idempotency_key is not null do nothing returning * into r;
  if r.id is not null then return next r; end if;
 end loop;
 return;
end $$;
revoke all on function public.claim_due_automations(text,int,int) from public,anon,authenticated;
grant execute on function public.claim_due_automations(text,int,int) to service_role;

create or replace function public.claim_retry_automation_runs(worker text,batch_size int default 25,lease_seconds int default 300)
returns setof public.automation_runs language sql security definer set search_path=public as $$
 update public.automation_runs r set status='claimed',attempt=r.attempt+1,lease_owner=worker,lease_expires_at=now()+make_interval(secs=>greatest(30,least(lease_seconds,3600))),started_at=now(),error=null
 where r.id in (select x.id from public.automation_runs x join public.automations a on a.id=x.automation_id where a.enabled and ((x.status='retry_wait' and x.next_attempt_at<=now()) or (x.status in ('claimed','running') and x.lease_expires_at<=now())) order by coalesce(x.next_attempt_at,x.lease_expires_at) for update of x skip locked limit greatest(1,least(batch_size,100))) returning r.* $$;
revoke all on function public.claim_retry_automation_runs(text,int,int) from public,anon,authenticated;
grant execute on function public.claim_retry_automation_runs(text,int,int) to service_role;
insert into storage.buckets(id,name,public) values('backups','backups',false) on conflict(id) do nothing;

-- END 012_durable_automation_scheduler.sql

-- ============================================================================
-- BEGIN 013_delegate_runs.sql
-- ============================================================================

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

-- END 013_delegate_runs.sql

-- ============================================================================
-- BEGIN 014_rpc_pipelines.sql
-- ============================================================================

-- Capability-scoped declarative RPC pipelines. No arbitrary code execution.
create table if not exists public.rpc_pipelines(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,name text not null,description text not null default '',definition jsonb not null,status text not null default 'draft' check(status in('draft','active','archived')),version int not null default 1,created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(user_id,name,version));
create table if not exists public.rpc_pipeline_runs(id uuid primary key default gen_random_uuid(),pipeline_id uuid not null references public.rpc_pipelines on delete cascade,user_id uuid not null references auth.users on delete cascade,status text not null check(status in('running','waiting_approval','completed','failed','cancelled')),input jsonb not null default '{}',output jsonb,error text,created_at timestamptz not null default now(),completed_at timestamptz);
create table if not exists public.rpc_pipeline_steps(id uuid primary key default gen_random_uuid(),run_id uuid not null references public.rpc_pipeline_runs on delete cascade,user_id uuid not null references auth.users on delete cascade,ordinal int not null,step_key text not null,capability text not null,status text not null,result jsonb,error text,proposal_id text references public.action_proposals(id) on delete set null,started_at timestamptz,completed_at timestamptz,unique(run_id,step_key));
alter table public.rpc_pipelines enable row level security;alter table public.rpc_pipeline_runs enable row level security;alter table public.rpc_pipeline_steps enable row level security;
create policy "own rpc pipelines" on public.rpc_pipelines for all using(auth.uid()=user_id) with check(auth.uid()=user_id);create policy "own rpc pipeline runs" on public.rpc_pipeline_runs for all using(auth.uid()=user_id) with check(auth.uid()=user_id);create policy "own rpc pipeline steps" on public.rpc_pipeline_steps for all using(auth.uid()=user_id) with check(auth.uid()=user_id);

-- END 014_rpc_pipelines.sql

-- ============================================================================
-- BEGIN 015_internal_rpc.sql
-- ============================================================================

-- Exactly-once receipt cache for authenticated Brain-to-Runtime RPC effects.
create table if not exists public.internal_rpc_receipts(idempotency_key text primary key,user_id uuid not null references auth.users on delete cascade,capability text not null,status text not null check(status in('executing','completed','failed')),result jsonb,error text,created_at timestamptz not null default now(),updated_at timestamptz not null default now());
alter table public.internal_rpc_receipts enable row level security;
create policy "own internal rpc receipts" on public.internal_rpc_receipts for select using(auth.uid()=user_id);

-- END 015_internal_rpc.sql

-- ============================================================================
-- BEGIN 016_media_memory.sql
-- ============================================================================

-- Transparent owner-controlled media favorites and playback history.
create table if not exists public.media_tracks(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,provider text not null check(provider in('youtube_music')),title text not null,artist text,url text not null,is_favorite boolean not null default false,created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(user_id,provider,url));
create table if not exists public.media_play_history(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,track_id uuid references public.media_tracks on delete set null,provider text not null,title text not null,artist text,url text not null,played_at timestamptz not null default now());
alter table public.media_tracks enable row level security;alter table public.media_play_history enable row level security;
create policy "own media tracks" on public.media_tracks for all using(auth.uid()=user_id) with check(auth.uid()=user_id);create policy "own media history" on public.media_play_history for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create index if not exists media_favorites_idx on public.media_tracks(user_id,is_favorite,updated_at desc);create index if not exists media_history_idx on public.media_play_history(user_id,played_at desc);

-- END 016_media_memory.sql

