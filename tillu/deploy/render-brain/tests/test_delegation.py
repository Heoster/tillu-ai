import asyncio
from app import database as db
from app.capabilities import registry
from app import delegation

def test_delegates_only_execute_registered_reads(tmp_path,monkeypatch):
    db.DB_PATH=tmp_path/'delegate.db';db.init_db()
    async def reader(args,user_id):return {'value':args['value'],'user_id':user_id}
    registry.register_read('delegate_test_read','test read',['test'],reader)
    async def plan(messages,phase,max_tokens):
        return {'json':{'workstreams':[{'name':'A','objective':'one','tool_calls':[{'name':'delegate_test_read','args':{'value':1}},{'name':'delete_task','args':{'id':'unsafe'}}]},{'name':'B','objective':'two','tool_calls':[{'name':'delegate_test_read','args':{'value':2}}]}]},'route':{'provider':'test','model':'test'}}
    async def chat(messages,phase,max_tokens):return {'text':'Combined [1] [2]','route':{'provider':'test','model':'test'}}
    monkeypatch.setattr(delegation.gateway,'json_chat',plan);monkeypatch.setattr(delegation.gateway,'chat',chat)
    result=asyncio.run(delegation.execute_delegates('owner','a sufficiently detailed research objective',2))
    assert result['status']=='completed'
    stored=db.get_delegate_run(result['id'],'owner')
    assert len(stored['workstreams'])==2
    assert all(call['name']=='delegate_test_read' for row in stored['workstreams'] for call in row['tool_calls'])
