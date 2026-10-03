import asyncio
from app import database as db
from app.capabilities import registry
from app.pipeline import validate_definition,execute_pipeline,resume_pipeline

def test_pipeline_reads_and_stops_for_action_approval(tmp_path):
    db.DB_PATH=tmp_path/'pipe.db';db.init_db()
    async def echo(args,user_id):return {'value':args['value'],'owner':user_id}
    registry.register_read('pipeline_echo','echo',['test'],echo)
    definition={'steps':[{'id':'read','capability':'pipeline_echo','args':{'value':'$input.value'}},{'id':'write','capability':'create_task','args':{'title':'$steps.read.value'}}]}
    validate_definition(definition)
    pipeline={'id':'p','definition':definition}
    result=asyncio.run(execute_pipeline(pipeline,'owner',{'value':'Study optics'}))
    assert result['status']=='waiting_approval'
    run=db.get_rpc_run(result['id'],'owner')
    assert run['steps'][0]['status']=='completed'
    assert run['steps'][1]['status']=='waiting_approval'
    assert run['steps'][1]['proposal_id']
    assert db.claim_action_proposal(run['steps'][1]['proposal_id'],'owner')
    db.finish_action_proposal(run['steps'][1]['proposal_id'],'owner','completed',{'id':'task-1'})
    resumed=asyncio.run(resume_pipeline(pipeline,'owner',result['id']))
    assert resumed['status']=='completed'
    assert resumed['steps']['write']['id']=='task-1'

def test_parallel_read_group(tmp_path):
    db.DB_PATH=tmp_path/'parallel.db';db.init_db()
    async def echo(args,user_id):return {'value':args['value']}
    registry.register_read('pipeline_parallel_echo','echo',['test'],echo)
    definition={'steps':[{'id':'a','capability':'pipeline_parallel_echo','parallel_group':'g','args':{'value':1}},{'id':'b','capability':'pipeline_parallel_echo','parallel_group':'g','args':{'value':2}}]}
    result=asyncio.run(execute_pipeline({'id':'p2','definition':definition},'owner',{}))
    assert result['status']=='completed' and result['steps']['a']['value']==1 and result['steps']['b']['value']==2

def test_pipeline_rejects_parallel_action():
    try:validate_definition({'steps':[{'id':'x','capability':'create_task','args':{'title':'x'},'parallel_group':'g'}]})
    except ValueError as exc:assert 'cannot run in parallel' in str(exc)
    else:raise AssertionError('unsafe parallel action accepted')
