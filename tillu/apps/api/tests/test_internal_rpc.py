import json
import pytest
from app.config import settings
from app.internal_rpc import signed_headers,verify_headers,_seen
from app import database as db

def test_internal_rpc_signature_and_replay(monkeypatch):
    monkeypatch.setattr(settings,'tillu_internal_secret','x'*32);monkeypatch.setattr(settings,'service_role','brain');_seen.clear()
    body=json.dumps({'capability':'browser_ready'}).encode();headers=signed_headers(body,'runtime')
    assert verify_headers(body,headers,'runtime')['source']=='brain'
    with pytest.raises(PermissionError):verify_headers(body,headers,'runtime')

def test_internal_rpc_idempotency_receipt(tmp_path):
    db.DB_PATH=tmp_path/'rpc.db';db.init_db();claimed,row=db.claim_internal_rpc('proposal-1','owner','browser_action',db.new_now());assert claimed
    claimed,row=db.claim_internal_rpc('proposal-1','owner','browser_action',db.new_now());assert not claimed and row['status']=='executing'
    db.finish_internal_rpc('proposal-1','owner','completed',{'ok':True},None,db.new_now());claimed,row=db.claim_internal_rpc('proposal-1','owner','browser_action',db.new_now());assert not claimed and row['result']=={'ok':True}
