from __future__ import annotations
import json
from datetime import datetime,timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from .repository import list_tasks,list_events,load_progress,list_memories,list_automation_runs,save_notification,save_delivery_attempt,save_briefing,list_push_subscriptions
from .sources import sources
from .providers import gateway
from .automation_runtime import next_run
from .persona import task_prompt
from .config import settings

def now():return datetime.now(timezone.utc).isoformat()

def default_briefings(user_id,timezone_name='Asia/Kolkata'):
 stamp=now();specs=[('Morning plan','morning_plan','0 7 * * *'),('Evening review','evening_review','0 20 * * *'),('Urgent alerts','urgent_alerts','*/15 * * * *'),('Study review','study_review','0 18 * * 0'),('Failed-run alerts','failed_runs','*/10 * * * *')];rows=[]
 for name,kind,schedule in specs:
  row={'id':str(uuid4()),'user_id':user_id,'name':name,'kind':kind,'schedule':schedule,'timezone':timezone_name,'channels':['in_app','web_push','gmail','whatsapp'],'config':{},'enabled':1,'next_run_at':next_run(schedule),'last_run_at':None,'created_at':stamp,'updated_at':stamp};save_briefing(row);rows.append(row)
 return rows

async def compose_briefing(row):
 uid=row['user_id'];kind=row['kind'];tasks=list_tasks(uid);events=list_events(uid);progress=load_progress();memories=list_memories(uid,'routines')+list_memories(uid,'preferences')
 weather=None;news=None;runs=list_automation_runs(uid,20)
 if kind=='morning_plan':weather=await sources.weather(settings.default_latitude,settings.default_longitude);news=await sources.news('India education technology',5)
 context={'kind':kind,'tasks':tasks[:20],'events':events[:20],'progress':progress,'routines':memories[:20],'weather':weather,'news':news,'failed_runs':[x for x in runs if x.get('status')=='failed'][:10]}
 deterministic={'morning_plan':f"You have {sum(x.get('status')!='done' for x in tasks)} active tasks and {len(events)} calendar events. Review priorities and the schedule below.",'evening_review':f"Today’s review: {sum(x.get('status')=='done' for x in tasks)} tasks completed; {sum(x.get('status')!='done' for x in tasks)} remain active.",'urgent_alerts':f"Urgent check completed. {sum(x.get('priority',2)==1 and x.get('status')!='done' for x in tasks)} high-priority tasks are active.",'study_review':f"Study review is ready across {len(progress)} tracked topics.",'failed_runs':f"Automation health check completed. {len(context['failed_runs'])} recent runs failed."}[kind]
 live=None
 try:live=await gateway.chat([{'role':'system','content':task_prompt('Create a concise private briefing for Heoster. Use only supplied data. Give prioritized action items and never claim an action was executed.')},{'role':'user','content':json.dumps(context,default=str)[:30000]}],phase='execution',max_tokens=900)
 except Exception:pass
 return {'title':row['name'],'body':live['text'] if live else deterministic,'data':context,'provider':live['provider'] if live else 'deterministic'}

async def run_briefing(row):
 content=await compose_briefing(row);stamp=now();nid=str(uuid4());notification={'id':nid,'user_id':row['user_id'],'briefing_id':row['id'],'kind':row['kind'],'title':content['title'],'body':content['body'],'data':{'provider':content['provider'],'context':content['data']},'priority':'urgent' if row['kind'] in {'urgent_alerts','failed_runs'} else 'normal','status':'unread','created_at':stamp,'read_at':None};save_notification(notification)
 for channel in row.get('channels') or ['in_app']:
  if channel=='in_app':status='delivered';error=None
  elif channel=='web_push':
   subscriptions=list_push_subscriptions(row['user_id'])
   if not (settings.vapid_private_key and settings.vapid_public_key):status='disabled';error='Web Push VAPID delivery is not configured'
   elif not subscriptions:status='disabled';error='No active push subscription'
   else:
    try:
     from pywebpush import webpush
     payload=json.dumps({'title':content['title'],'body':content['body'],'notification_id':nid})
     for subscription in subscriptions:webpush(subscription_info=subscription['subscription'],data=payload,vapid_private_key=settings.vapid_private_key,vapid_claims={'sub':settings.vapid_subject})
     status='delivered';error=None
    except Exception as exc:status='failed';error=f'{type(exc).__name__}: {str(exc)[:200]}'
  else:status='proposal_required';error='External delivery requires per-run approval by policy'
  save_delivery_attempt({'id':str(uuid4()),'notification_id':nid,'user_id':row['user_id'],'channel':channel,'status':status,'attempt':1,'error':error,'external_id':None,'created_at':stamp,'updated_at':stamp})
 updated={**row,'last_run_at':stamp,'next_run_at':next_run(row['schedule']),'updated_at':stamp};save_briefing(updated)
 return notification
