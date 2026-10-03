import json
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from croniter import croniter
from .sources import sources
from .providers import gateway
from .persona import task_prompt
from .repository import save_automation_run,update_automation,create_action_proposal,save_nudge,save_notification,save_delivery_attempt,list_push_subscriptions
from .config import settings

def now():return datetime.now(timezone.utc).isoformat()
def next_run(schedule,base=None,timezone_name='Asia/Kolkata'):
    tz=ZoneInfo(timezone_name);local=(base or datetime.now(timezone.utc)).astimezone(tz);return croniter(schedule,local).get_next(datetime).astimezone(timezone.utc).isoformat()
async def execute_automation(a,claimed_run_id=None,scheduled_for=None):
    stamp=now();run={"id":claimed_run_id or str(uuid4()),"automation_id":a["id"],"user_id":a["user_id"],"status":"running","output":None,"error":None,"started_at":stamp,"completed_at":None,"scheduled_for":scheduled_for,"idempotency_key":f'{a["id"]}:{scheduled_for}' if scheduled_for else None,"attempt":int(a.get('attempt',1)),"lease_owner":None,"lease_expires_at":None,"next_attempt_at":None,"cancelled_at":None};save_automation_run(run)
    try:
        action=a["action_type"]
        if action=="nightly_backup":
            pid=str(uuid4());create_action_proposal({'id':pid,'user_id':a['user_id'],'kind':'automation_backup','payload':{'automation_id':a['id'],'scheduled_for':scheduled_for},'status':'pending','created_at':stamp,'expires_at':(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()});output=f'Backup proposal {pid} requires approval.';run.update(status='proposal_required',output=output,completed_at=now())
        else:
            if action=="weather_brief":data=await sources.weather();context=json.dumps(data)[:12000]
            elif action=="news_digest":data=await sources.news(a.get("config",{}).get("query","India technology education"));context=json.dumps(data)[:16000]
            elif action=="study_review":context="Create a concise study-review reminder based on configured study goals."
            elif action=="weekly_audit":context="Create a read-only weekly audit report. Do not change data or contact anyone."
            else:
                weather=await sources.weather();trends=await sources.hacker_news(7);context=json.dumps({"weather":weather,"trends":trends})[:18000]
            live=await gateway.chat([{"role":"system","content":task_prompt("Create a concise, actionable personal briefing for Heoster. Use only supplied data and identify source names.")},{"role":"user","content":context}])
            if not live:raise RuntimeError('No hosted AI provider is configured')
            output=live["text"]
            config=a.get('config',{});channels=config.get('channels',['in_app']);nid=str(uuid4());save_notification({'id':nid,'user_id':a['user_id'],'briefing_id':None,'kind':'automation','title':a['name'],'body':output,'data':{'automation_id':a['id'],'run_id':run['id']},'priority':'normal','status':'unread','created_at':now(),'read_at':None})
            if 'in_app' in channels:save_delivery_attempt({'id':str(uuid4()),'notification_id':nid,'user_id':a['user_id'],'channel':'in_app','status':'delivered','attempt':1,'error':None,'external_id':None,'created_at':now(),'updated_at':now()})
            if 'web_push' in channels:
                status='disabled';error='Web Push is not configured or no subscription exists'
                if settings.vapid_private_key and settings.vapid_public_key and list_push_subscriptions(a['user_id']):
                    try:
                        from pywebpush import webpush
                        for sub in list_push_subscriptions(a['user_id']):webpush(subscription_info=sub['subscription'],data=json.dumps({'title':a['name'],'body':output,'notification_id':nid}),vapid_private_key=settings.vapid_private_key,vapid_claims={'sub':settings.vapid_subject})
                        status='delivered';error=None
                    except Exception as exc:status='failed';error=f'{type(exc).__name__}: {str(exc)[:200]}'
                save_delivery_attempt({'id':str(uuid4()),'notification_id':nid,'user_id':a['user_id'],'channel':'web_push','status':status,'attempt':1,'error':error,'external_id':None,'created_at':now(),'updated_at':now()})
            external=[x for x in channels if x not in {'in_app','web_push'}];proposal_ids=[]
            for channel in external:
                pid=str(uuid4())
                if channel=='gmail':
                    if not config.get('gmail_to'):raise ValueError('gmail_to is required for Gmail delivery')
                    kind='gmail_draft';payload={'to':config['gmail_to'],'subject':a['name'],'body':output}
                elif channel=='whatsapp':
                    if not config.get('whatsapp_to'):raise ValueError('whatsapp_to is required for WhatsApp delivery')
                    kind='whatsapp_send';payload={'to':config['whatsapp_to'],'body':output}
                else:continue
                create_action_proposal({'id':pid,'user_id':a['user_id'],'kind':kind,'payload':payload,'status':'pending','created_at':stamp,'expires_at':(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()});proposal_ids.append(pid)
            run.update(status='proposal_required' if proposal_ids else 'completed',output=output,completed_at=now())
        save_automation_run(run)
    except Exception as exc:
        policy=a.get('retry_policy') or {};attempt=int(run.get('attempt',1));maximum=max(1,min(int(policy.get('max_attempts',3)),10));delay=max(10,min(int(policy.get('base_delay_seconds',60))*(2**(attempt-1)),86400));retry=(datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat() if attempt<maximum else None
        run.update(status="retry_wait" if retry else "failed",error=f"{type(exc).__name__}: {str(exc)[:300]}",next_attempt_at=retry,completed_at=now());save_automation_run(run)
        if not retry:
            save_nudge({'id':str(uuid4()),'user_id':a['user_id'],'kind':'automation_failure','title':f"Automation failed: {a['name']}",'body':run['error'],'evidence':{'automation_id':a['id'],'run_id':run['id'],'attempt':attempt},'status':'pending','due_at':now(),'created_at':now()})
    update_automation(a["id"],a["user_id"],{"last_run_at":run["completed_at"],"next_run_at":next_run(a["schedule"],timezone_name=a.get('timezone','Asia/Kolkata')) if a.get("schedule") else None})
    return run
