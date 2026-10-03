from uuid import uuid4
from app import database as db


def setup_store(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'contract.db');db.init_db()


def test_rich_message_metadata_round_trip(tmp_path,monkeypatch):
    setup_store(tmp_path,monkeypatch);uid=str(uuid4());cid=str(uuid4())
    assert db.ensure_conversation(cid,uid,'Contract','2026-10-01T00:00:00+00:00')
    metadata={'tools':['calculator'],'widgets':[{'type':'calculation','result':4}],'citations':[],'provider':'test'}
    db.add_message(cid,'assistant','Four','2026-10-01T00:00:01+00:00',metadata)
    rows=db.conversation_messages(cid,uid)
    assert rows[0]['content']=='Four'
    assert rows[0]['metadata']==metadata


def test_task_contract_and_owner_scope(tmp_path,monkeypatch):
    setup_store(tmp_path,monkeypatch);uid=str(uuid4());other=str(uuid4());tid=str(uuid4())
    db.create_task({'id':tid,'user_id':uid,'title':'Original','subject':None,'due_at':None,'status':'todo','priority':2,'created_at':'2026-10-01T00:00:00+00:00'})
    assert db.patch_task(tid,uid,{'title':'Updated','status':'doing'})
    assert db.list_tasks(uid)[0]['title']=='Updated'
    assert not db.patch_task(tid,other,{'title':'Forbidden'})
    assert not db.delete_task(tid,other)
    assert db.delete_task(tid,uid)


def test_proposal_claim_is_single_use(tmp_path,monkeypatch):
    setup_store(tmp_path,monkeypatch);uid=str(uuid4());pid=str(uuid4())
    db.create_action_proposal({'id':pid,'user_id':uid,'kind':'delete_task','payload':{'id':str(uuid4())},'status':'pending','created_at':'2026-10-01T00:00:00+00:00','expires_at':'2026-10-02T00:00:00+00:00'})
    assert db.claim_action_proposal(pid,uid)
    assert not db.claim_action_proposal(pid,uid)
    assert db.finish_action_proposal(pid,uid,'completed',{'ok':True})
