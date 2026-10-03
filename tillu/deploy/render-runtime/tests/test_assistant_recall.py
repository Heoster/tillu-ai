import asyncio
from app import database as db
from app.orchestrator import route_tools,session_context

def test_cross_session_recall_tool_is_selected_and_owner_scoped(tmp_path):
    db.DB_PATH=tmp_path/'recall.db';db.init_db();n=db.new_now()
    db.ensure_conversation('mine','owner','Optics',n);db.add_message('mine','user','We discussed diffraction revision',n)
    db.ensure_conversation('other','other-user','Private',n);db.add_message('other','user','Secret diffraction material',n)
    assert any(x['name']=='session_search' for x in route_tools('What did we discuss in the previous session about diffraction?'))
    result=asyncio.run(session_context({'query':'diffraction'},'owner'))
    assert len(result['results'])==1 and result['results'][0]['conversation_id']=='mine'

def test_complexity_can_select_delegation():
    tools=route_tools('Research and compare multiple alternatives and evaluate their pros and cons using sources')
    assert any(x['name']=='parallel_delegates' for x in tools)
