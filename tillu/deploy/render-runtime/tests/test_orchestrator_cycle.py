import asyncio
from app.orchestrator import orchestrate

def test_bounded_cycle_executes_and_verifies_calculation():
    result=asyncio.run(orchestrate('calculate 7*8+1','00000000-0000-0000-0000-000000000001'))
    phases=[x['phase'] for x in result['cycle']]
    assert phases[:2]==['intent','planning']
    assert 'verification' in phases
    assert result['tool_results'][0]['tool']=='calculator'
    assert result['tool_results'][0]['data']['result']==57
    assert result.get('iteration',0)<=2

def test_empty_evidence_retries_are_bounded():
    result=asyncio.run(orchestrate('uploaded document impossible phrase','00000000-0000-0000-0000-000000000001'))
    assert result.get('iteration',0)==2
    assert sum(1 for x in result['cycle'] if x['phase']=='replan')==2
