from pathlib import Path

def test_unified_supabase_schema_contains_all_migrations_in_order():
    root=Path(__file__).resolve().parents[3];schema=(root/'supabase/schema.sql').read_text();positions=[]
    for n in range(1,17):
        prefix=f'-- BEGIN {n:03d}_';position=schema.find(prefix);assert position>=0,prefix;positions.append(position)
    assert positions==sorted(positions)
    assert 'enable row level security' in schema.lower()
    assert 'claim_due_automations' in schema
    assert 'internal_rpc_receipts' in schema
    assert 'proposal_id text references public.action_proposals(id)' in schema
    assert 'proposal_id uuid references public.action_proposals' not in schema
