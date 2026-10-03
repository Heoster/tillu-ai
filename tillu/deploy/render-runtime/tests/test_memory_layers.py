from uuid import uuid4
from app import database as db
from app.main import infer_natural_action

UID='00000000-0000-0000-0000-000000000001'

def test_layered_memory_round_trip_and_owner_delete(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'memory.db');db.init_db();mid=str(uuid4());stamp='2026-10-01T00:00:00+00:00'
    row={'id':mid,'user_id':UID,'layer':'people','key':'Aman','value':{'name':'Aman','email':'aman@example.com'},'sensitivity':'sensitive','source':'explicit_chat','confidence':1,'status':'active','created_at':stamp,'updated_at':stamp,'last_used_at':None}
    db.save_memory(row);stored=db.list_memories(UID,'people')
    assert stored[0]['value']['email']=='aman@example.com'
    assert not db.delete_memory(mid,str(uuid4()))
    assert db.delete_memory(mid,UID)

def test_friend_and_preference_memory_are_approval_proposals(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'memory-actions.db');db.init_db()
    friend=infer_natural_action("remember my friend Aman email is aman@example.com",UID)
    like=infer_natural_action('remember that I like dark minimal interfaces',UID)
    assert friend['kind']=='create_memory' and friend['payload']['layer']=='people' and friend['payload']['sensitivity']=='sensitive'
    assert like['kind']=='create_memory' and like['payload']['layer']=='preferences'
