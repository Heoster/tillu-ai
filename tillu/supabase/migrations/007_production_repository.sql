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
