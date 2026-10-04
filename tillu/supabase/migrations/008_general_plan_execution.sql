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
