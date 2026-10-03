import asyncio
import pytest
from app import database as db
from app.capabilities import registry
from app.config import settings
from app.safe_python import issue_token,run_safe_python

def test_safe_python_subset_calls_scoped_reads(tmp_path,monkeypatch):
    db.DB_PATH=tmp_path/'rpc.db';db.init_db();monkeypatch.setattr(settings,'rpc_capability_secret','test-secret')
    async def echo(args,user_id):return {'text':args['text'],'owner':user_id}
    registry.register_read('rpc_echo','echo',['test'],echo)
    token=issue_token('owner',['rpc_echo'],60)
    result=asyncio.run(run_safe_python("x = tool('rpc_echo', {'text': 'hello'})",token,'owner'))
    assert result['variables']['x']['text']=='hello'

def test_safe_python_subset_rejects_import_and_scope(tmp_path,monkeypatch):
    db.DB_PATH=tmp_path/'rpc2.db';db.init_db();monkeypatch.setattr(settings,'rpc_capability_secret','test-secret')
    token=issue_token('owner',['create_task'],60)
    with pytest.raises(ValueError):asyncio.run(run_safe_python('import os',token,'owner'))
    with pytest.raises(PermissionError):asyncio.run(run_safe_python("tool('delete_task', {'id':'x'})",token,'owner'))

def test_safe_python_action_becomes_proposal(tmp_path,monkeypatch):
    db.DB_PATH=tmp_path/'rpc3.db';db.init_db();monkeypatch.setattr(settings,'rpc_capability_secret','test-secret')
    token=issue_token('owner',['create_task'],60)
    result=asyncio.run(run_safe_python("tool('create_task', {'title':'Review optics'})",token,'owner'))
    assert result['outputs'][0]['status']=='waiting_approval'
    assert db.get_action_proposal(result['outputs'][0]['proposal_id'],'owner')['status']=='pending'
