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
