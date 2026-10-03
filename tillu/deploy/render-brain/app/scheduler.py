"""Natural-language automation compiler and scheduler validation."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from croniter import croniter
from .providers import gateway

ACTIONS={'daily_brief','weather_brief','news_digest','study_review','weekly_audit','nightly_backup'}
CHANNELS={'in_app','web_push','gmail','whatsapp'}

def validate_schedule(schedule:str,timezone:str)->dict:
    try:tz=ZoneInfo(timezone)
    except ZoneInfoNotFoundError:raise ValueError('Unknown IANA timezone')
    if not croniter.is_valid(schedule):raise ValueError('Invalid five-field cron schedule')
    if len(schedule.split())!=5:raise ValueError('Only five-field cron schedules are supported')
    nxt=croniter(schedule,datetime.now(tz)).get_next(datetime)
    return {'schedule':schedule,'timezone':timezone,'next_run_at':nxt.astimezone(ZoneInfo('UTC')).isoformat()}

def _deterministic(text:str,timezone:str):
    q=text.lower();hour=7;minute=0
    m=re.search(r'\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b',q)
    if m:
        hour=int(m.group(1));minute=int(m.group(2) or 0);ampm=m.group(3)
        if ampm=='pm' and hour<12:hour+=12
        if ampm=='am' and hour==12:hour=0
        if hour>23 or minute>59:raise ValueError('Invalid requested time')
    if 'nightly' in q or 'every night' in q: schedule=f'{minute} {hour if m else 2} * * *';action='nightly_backup' if 'backup' in q else 'daily_brief'
    elif 'weekly' in q:
        days={'sunday':0,'monday':1,'tuesday':2,'wednesday':3,'thursday':4,'friday':5,'saturday':6};day=next((v for k,v in days.items() if k in q),1);schedule=f'{minute} {hour} * * {day}';action='weekly_audit' if 'audit' in q else 'study_review'
    elif 'daily' in q or 'every day' in q:
        schedule=f'{minute} {hour} * * *';action='weather_brief' if 'weather' in q else 'news_digest' if 'news' in q else 'daily_brief'
    else:return None
    channels=[x for x in CHANNELS if x.replace('_',' ') in q or x in q]
    return {'name':text[:100],'schedule':schedule,'timezone':timezone,'action_type':action,'config':{'channels':channels or ['in_app'],'request':text},'enabled':True}

async def compile_automation(text:str,timezone='Asia/Kolkata')->dict:
    draft=_deterministic(text,timezone)
    if not draft:
        result=await gateway.json_chat([{'role':'system','content':'Compile a natural-language recurring automation. Return JSON only with name, schedule (five-field cron), timezone (IANA), action_type, config, enabled. action_type must be one of: '+', '.join(sorted(ACTIONS))+'. Delivery channels may only be in_app, web_push, gmail, whatsapp. Do not invent recipients.'},{'role':'user','content':text}],phase='planning',max_tokens=500)
        if not result:raise RuntimeError('No hosted AI provider is configured')
        draft=result['json'];draft.setdefault('timezone',timezone);draft.setdefault('enabled',True);draft.setdefault('config',{})
    if draft.get('action_type') not in ACTIONS:raise ValueError('Unsupported automation action')
    channels=draft.get('config',{}).get('channels',['in_app'])
    if not isinstance(channels,list) or set(channels)-CHANNELS:raise ValueError('Unsupported delivery channel')
    checked=validate_schedule(str(draft.get('schedule','')),str(draft.get('timezone',timezone)))
    return {**draft,**checked}
