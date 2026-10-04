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
