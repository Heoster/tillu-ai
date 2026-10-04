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
