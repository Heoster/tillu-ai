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
