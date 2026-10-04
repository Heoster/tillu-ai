import asyncio
from app import database as db
from app.proactive import default_briefings,run_briefing

UID='00000000-0000-0000-0000-000000000001'

def test_full_default_suite_and_durable_inbox(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'briefings.db');db.init_db()
    rows=default_briefings(UID)
    assert {x['kind'] for x in rows}=={'morning_plan','evening_review','urgent_alerts','study_review','failed_runs'}
    evening=next(x for x in db.list_briefings(UID) if x['kind']=='evening_review')
    notification=asyncio.run(run_briefing(evening))
    assert notification['status']=='unread'
    stored=db.list_notifications(UID,'unread')
    assert stored[0]['id']==notification['id']
    assert db.update_notification(notification['id'],UID,'read','2026-10-01T00:00:00+00:00')
    assert db.list_notifications(UID,'read')[0]['status']=='read'
