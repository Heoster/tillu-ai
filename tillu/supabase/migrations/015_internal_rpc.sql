-- Exactly-once receipt cache for authenticated Brain-to-Runtime RPC effects.
create table if not exists public.internal_rpc_receipts(idempotency_key text primary key,user_id uuid not null references auth.users on delete cascade,capability text not null,status text not null check(status in('executing','completed','failed')),result jsonb,error text,created_at timestamptz not null default now(),updated_at timestamptz not null default now());
alter table public.internal_rpc_receipts enable row level security;
create policy "own internal rpc receipts" on public.internal_rpc_receipts for select using(auth.uid()=user_id);
