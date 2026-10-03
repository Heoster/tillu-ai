import asyncio
from uuid import uuid4
from app import database as db
from app.auth import User
from app.main import approve,ApprovalRequest
from app.models import ActionPlan,PlanCall,Risk


def test_approved_plan_executes_registered_calls_once(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'plans.db');db.init_db()
    uid='00000000-0000-0000-0000-000000000001';plan_id=str(uuid4());run_id=str(uuid4())
    plan=ActionPlan(id=plan_id,title='Workspace setup',summary='Create two owned resources',steps=['Create task','Create canvas'],calls=[PlanCall(capability='create_task',args={'title':'Plan task'}),PlanCall(capability='create_canvas',args={'title':'Plan canvas'})],risk=Risk.write,needs_approval=True)
    db.save_plan(plan.model_dump(),uid,run_id)
    result=asyncio.run(approve(plan_id,ApprovalRequest(approved=True),User(uid,'heoster@local')))
    assert result['job'].status=='completed'
    assert result['job'].progress==100
    assert [x['capability'] for x in result['job'].result['steps']]==['create_task','create_canvas']
    assert db.list_tasks(uid)[0]['title']=='Plan task'
    assert db.list_canvases(uid)[0]['title']=='Plan canvas'
    # Whole-plan approval is atomically single use.
    try:asyncio.run(approve(plan_id,ApprovalRequest(approved=True),User(uid,'heoster@local')))
    except Exception as exc:assert getattr(exc,'status_code',None)==409
    else:raise AssertionError('plan executed twice')
