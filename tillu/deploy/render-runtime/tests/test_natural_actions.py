from uuid import uuid4
from app import database as db
from app.main import infer_natural_action

UID='00000000-0000-0000-0000-000000000001'

def setup(tmp_path,monkeypatch):monkeypatch.setattr(db,'DB_PATH',tmp_path/'natural.db');db.init_db()

def test_natural_creation_forms_do_not_need_exact_commands(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch)
    cases=[('remind me to revise electrostatics','create_task'),('remember that Gauss law needs revision','create_memory'),('make a canvas for ray diagrams','create_canvas'),('save https://example.com as a research source','save_research_source'),('schedule event Physics revision tomorrow at 6 pm','create_event'),('message +919999999999 on whatsapp saying I will call later','whatsapp_send'),('draft an email to teacher@example.com with subject Project saying I have completed it','gmail_draft'),('mark topic phy-optics as mastered','update_progress'),('create a daily weather brief called Morning Update at 7 am','create_automation')]
    for text,kind in cases:
        proposal=infer_natural_action(text,UID)
        assert proposal and proposal['kind']==kind
        assert proposal['status']=='pending'

def test_natural_resource_resolution_is_owner_scoped(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch);tid=str(uuid4())
    db.create_task({'id':tid,'user_id':UID,'title':'Revise optics','subject':None,'due_at':None,'status':'todo','priority':2,'created_at':'2026-10-01T00:00:00+00:00'})
    proposal=infer_natural_action('complete task Revise optics',UID)
    assert proposal['kind']=='update_task' and proposal['payload']=={'id':tid,'status':'done'}
    # Unknown resources fail closed instead of guessing.
    assert infer_natural_action('delete task Something else',UID) is None
