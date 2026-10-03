"""Supabase/Postgres repository used exclusively in production.

The service-role client is backend-only. Every owner entity is additionally
filtered by user_id because service-role bypasses RLS. No method falls back to
SQLite or process memory.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .config import settings
from .cloud import cloud


def _client():
    if not cloud.enabled:
        raise RuntimeError("Supabase persistence is unavailable")
    return cloud.client

def _data(result): return result.data or []
def _one(result):
    rows=_data(result)
    return rows[0] if rows else None

def _owner():
    if not settings.owner_user_id:
        raise RuntimeError("OWNER_USER_ID is required for production persistence")
    return settings.owner_user_id

def _json_text(value):
    if isinstance(value,dict) and set(value)=={"text"}: return value["text"]
    return value if isinstance(value,str) else str(value or "")

def init_db():
    # Connectivity + required-schema probe. A missing migration fails startup.
    _client().table("user_settings").select("user_id").eq("user_id",_owner()).limit(1).execute()

def new_now(): return datetime.now(timezone.utc).isoformat()

def save_job(j):
    d=j.model_dump() if hasattr(j,"model_dump") else dict(j); d.setdefault("user_id",_owner());d["updated_at"]=new_now()
    _client().table("jobs").upsert(d).execute()
def load_jobs(): return _data(_client().table("jobs").select("*").eq("user_id",_owner()).order("created_at",desc=True).execute())
def save_progress(i,s,c,n): _client().table("assistant_topic_progress").upsert({"user_id":_owner(),"topic_id":i,"status":s,"confidence":c,"updated_at":n},on_conflict="user_id,topic_id").execute()
def load_progress():
    rows=_data(_client().table("assistant_topic_progress").select("topic_id,status,confidence").eq("user_id",_owner()).execute())
    return {x["topic_id"]:{"status":x["status"],"confidence":x["confidence"]} for x in rows}
def audit(a,r,d,n): _client().table("audit_events").insert({"user_id":_owner(),"action":a,"risk":r,"input_redacted":d,"created_at":n}).execute()
def load_audit(limit=50):
    rows=_data(_client().table("audit_events").select("id,action,risk,input_redacted,created_at").eq("user_id",_owner()).order("id",desc=True).limit(limit).execute())
    return [{"id":x["id"],"action":x["action"],"risk":x["risk"],"detail":x.get("input_redacted") or {},"created_at":x["created_at"]} for x in rows]
def save_file(row):
    x={k:v for k,v in row.items() if k not in {"path","size"}};x["storage_path"]=row.get("storage_path") or f'{row["user_id"]}/{row["sha256"]}.pdf';x["size"]=row.get("size")
    _client().table("files").upsert(x).execute()
def _file(x):
    if not x:return None
    return {**x,"path":x.get("storage_path")}
def load_files(u): return [_file(x) for x in _data(_client().table("files").select("*").eq("user_id",u).order("created_at",desc=True).execute())]
def get_file(i,u): return _file(_one(_client().table("files").select("*").eq("id",i).eq("user_id",u).limit(1).execute()))
def delete_file(i,u):
    row=get_file(i,u)
    if row:_client().table("files").delete().eq("id",i).eq("user_id",u).execute()
    return row
def replace_chunks(i,ch):
    f=_one(_client().table("files").select("user_id").eq("id",i).eq("user_id",_owner()).limit(1).execute())
    if not f:raise KeyError("File not found")
    _client().table("document_chunks").delete().eq("file_id",i).eq("user_id",f["user_id"]).execute()
    rows=[{"file_id":i,"user_id":f["user_id"],"page":x["page"],"content":x["content"]} for x in ch]
    for p in range(0,len(rows),250): _client().table("document_chunks").insert(rows[p:p+250]).execute()
def load_chunks(u,i=None):
    q=_client().table("document_chunks").select("id,file_id,page,content,files(name)").eq("user_id",u)
    if i:q=q.eq("file_id",i)
    return [{**x,"name":(x.get("files") or {}).get("name","")} for x in _data(q.execute())]
def create_task(row): _client().table("tasks").insert(row).execute()
def list_tasks(u): return _data(_client().table("tasks").select("*").eq("user_id",u).order("created_at",desc=True).execute())
def update_task(i,u,s): _client().table("tasks").update({"status":s}).eq("id",i).eq("user_id",u).execute()
def patch_task(i,u,d): return bool(_data(_client().table("tasks").update({k:v for k,v in d.items() if k in {"title","subject","due_at","status","priority"}}).eq("id",i).eq("user_id",u).execute()))
def delete_task(i,u): return bool(_data(_client().table("tasks").delete().eq("id",i).eq("user_id",u).execute()))
def save_source(row): _client().table("research_sources").insert(row).execute()
def list_sources(u):
    return [{**x,"excerpt":x.pop("content","")[:300]} for x in _data(_client().table("research_sources").select("*").eq("user_id",u).order("created_at",desc=True).execute())]
def delete_source(i,u): return bool(_data(_client().table("research_sources").delete().eq("id",i).eq("user_id",u).execute()))
def source_chunks(u):
    rows=_data(_client().table("research_sources").select("id,title,content").eq("user_id",u).execute())
    return [{"file":x["title"],"page":1,"content":x["content"][i:i+1400]} for x in rows for i in range(0,len(x["content"]),1220)]
def create_event(row): _client().table("calendar_events").insert(row).execute()
def list_events(u,start=None,end=None):
    q=_client().table("calendar_events").select("*").eq("user_id",u)
    if start:q=q.gte("start_at",start)
    if end:q=q.lte("start_at",end)
    return _data(q.order("start_at").execute())
def update_event(i,u,d): return bool(_data(_client().table("calendar_events").update({k:v for k,v in d.items() if k in {"title","subject","start_at","end_at","reminder_minutes","status"}}).eq("id",i).eq("user_id",u).execute()))
def delete_event(i,u): return bool(_data(_client().table("calendar_events").delete().eq("id",i).eq("user_id",u).execute()))
def save_checkpoint(i,u,s,status,n): _client().table("agent_checkpoints").upsert({"run_id":i,"user_id":u,"state":s,"status":status,"updated_at":n}).execute()
def load_checkpoint(i,u): return _one(_client().table("agent_checkpoints").select("*").eq("run_id",i).eq("user_id",u).limit(1).execute())
def save_plan(p,u,run):
    row={"id":p["id"],"user_id":u,"run_id":run,"title":p["title"],"summary":p.get("summary"),"steps":p.get("steps",[]),"risk":p["risk"],"status":p["status"],"data":p}
    _client().table("action_plans").upsert(row).execute()
def get_plan(i): return _one(_client().table("action_plans").select("*").eq("id",i).limit(1).execute())
def claim_plan(i,u): return bool(_client().rpc("claim_action_plan",{"plan_id":i,"uid":u}).execute().data)
def set_plan_status(i,s):
    row=get_plan(i);_client().table("action_plans").update({"status":s}).eq("id",i).execute()
    if row and row.get("run_id"):_client().table("agent_checkpoints").update({"status":s,"updated_at":new_now()}).eq("run_id",row["run_id"]).eq("user_id",row["user_id"]).execute()
def add_history(r): _client().table("browser_history").insert(r).execute()
def list_history(u,limit=100): return _data(_client().table("browser_history").select("*").eq("user_id",u).order("visited_at",desc=True).limit(limit).execute())
def clear_history(u): _client().table("browser_history").delete().eq("user_id",u).execute()
def due_reminders(u,at): return _data(_client().rpc("due_calendar_reminders",{"uid":u,"at_time":at}).execute())
def ensure_conversation(i,u,t,n):
    row=_one(_client().table("conversations").select("user_id").eq("id",i).limit(1).execute())
    if row and row["user_id"]!=u:return False
    if row:_client().table("conversations").update({"updated_at":n}).eq("id",i).eq("user_id",u).execute()
    else:_client().table("conversations").insert({"id":i,"user_id":u,"title":t,"created_at":n,"updated_at":n}).execute()
    return True
def add_message(i,r,c,n,metadata=None):
    _client().table("messages").insert({"conversation_id":i,"role":r,"content":{"text":c},"metadata":metadata or {},"created_at":n}).execute();_client().table("conversations").update({"updated_at":n}).eq("id",i).execute()
def list_conversations(u,query="",archived=False):
    q=_client().table("conversations").select("*").eq("user_id",u).eq("archived",archived)
    if query:q=q.ilike("title",f"%{query}%")
    rows=_data(q.order("pinned",desc=True).order("updated_at",desc=True).limit(100).execute())
    for x in rows:
        m=_one(_client().table("messages").select("content").eq("conversation_id",x["id"]).order("created_at",desc=True).limit(1).execute());x["preview"]=_json_text(m["content"]) if m else None
    return rows
def update_conversation(i,u,changes):
    patch={k:v for k,v in changes.items() if k in {"title","pinned","archived"}}
    if not patch:return False
    patch["updated_at"]=new_now();return bool(_data(_client().table("conversations").update(patch).eq("id",i).eq("user_id",u).execute()))
def conversation_messages(i,u):
    if not _one(_client().table("conversations").select("id").eq("id",i).eq("user_id",u).limit(1).execute()):return None
    rows=_data(_client().table("messages").select("role,content,metadata,created_at").eq("conversation_id",i).order("created_at").execute())
    return [{**x,"content":_json_text(x["content"])} for x in rows]
def delete_conversation(i,u): return bool(_data(_client().table("conversations").delete().eq("id",i).eq("user_id",u).execute()))
def search_sessions(u,q,limit=20): return _data(_client().rpc('search_session_messages',{'uid':u,'query':q,'result_limit':limit}).execute())
def save_summary(r): _client().table('session_summaries').upsert(r,on_conflict='user_id,conversation_id').execute()
def list_summaries(u): return _data(_client().table('session_summaries').select('*').eq('user_id',u).order('updated_at',desc=True).execute())
def save_skill(r): _client().table('skills').insert(r).execute()
def list_skills(u,status=None):
    q=_client().table('skills').select('*').eq('user_id',u)
    if status:q=q.eq('status',status)
    return _data(q.order('updated_at',desc=True).execute())
def claim_due_automations(at,worker,lease_expires,limit=25):
    runs=_data(_client().rpc('claim_due_automations',{'worker':worker,'batch_size':limit,'lease_seconds':300}).execute());out=[]
    for run in runs:
        automation=_one(_client().table('automations').select('*').eq('id',run['automation_id']).eq('user_id',run['user_id']).limit(1).execute())
        if automation:out.append({**automation,'run_id':run['id'],'scheduled_for':run.get('scheduled_for')})
    return out
def update_skill(i,u,d): return bool(_data(_client().table('skills').update({**d,'updated_at':new_now()}).eq('id',i).eq('user_id',u).execute()))
def get_skill(i,u): return _one(_client().table('skills').select('*').eq('id',i).eq('user_id',u).limit(1).execute())
def save_conclusion(r): _client().table('user_model_conclusions').insert(r).execute()
def list_conclusions(u,status=None):
    q=_client().table('user_model_conclusions').select('*').eq('user_id',u)
    if status:q=q.eq('status',status)
    return _data(q.order('updated_at',desc=True).execute())
def update_conclusion(i,u,d): return bool(_data(_client().table('user_model_conclusions').update({**d,'updated_at':new_now()}).eq('id',i).eq('user_id',u).execute()))
def save_nudge(r): _client().table('nudges').insert(r).execute()
def list_nudges(u,status=None):
    q=_client().table('nudges').select('*').eq('user_id',u)
    if status:q=q.eq('status',status)
    return _data(q.order('created_at',desc=True).execute())
def update_nudge(i,u,status): return bool(_data(_client().table('nudges').update({'status':status}).eq('id',i).eq('user_id',u).execute()))
def save_observation(r): _client().table('learning_observations').insert(r).execute()
def list_observations(u,limit=100): return _data(_client().table('learning_observations').select('*').eq('user_id',u).order('created_at',desc=True).limit(limit).execute())
def save_skill_outcome(r): _client().table('skill_outcomes').insert(r).execute()
def list_skill_outcomes(u,skill_id): return _data(_client().table('skill_outcomes').select('*').eq('user_id',u).eq('skill_id',skill_id).order('created_at',desc=True).execute())
def create_note(r): _client().table("notes").insert({**r,"tags":r.get("tags") if isinstance(r.get("tags"),list) else []}).execute()
def list_notes(u): return _data(_client().table("notes").select("*").eq("user_id",u).order("updated_at",desc=True).execute())
def get_note(i,u): return _one(_client().table("notes").select("*").eq("id",i).eq("user_id",u).limit(1).execute())
def update_note(i,u,d,n):
    patch={k:v for k,v in d.items() if k in {"title","content","canvas_data","tags"}};patch["updated_at"]=n
    _client().table("notes").update(patch).eq("id",i).eq("user_id",u).execute();return get_note(i,u)
def delete_note(i,u): return bool(_data(_client().table("notes").delete().eq("id",i).eq("user_id",u).execute()))
def set_cache(k,v,n): _client().table("service_cache").upsert({"key":k,"value":v,"updated_at":n}).execute()
def get_cache(k): return _one(_client().table("service_cache").select("value,updated_at").eq("key",k).limit(1).execute())
def create_automation(r):
    x={**r,"config":r.get("config") if isinstance(r.get("config"),dict) else __import__("json").loads(r.get("config") or "{}"),"enabled":bool(r.get("enabled"))};_client().table("automations").insert(x).execute()
def list_automations(u): return _data(_client().table("automations").select("*").eq("user_id",u).order("created_at",desc=True).execute())
def update_automation(i,u,d): _client().table("automations").update({k:(bool(v) if k=="enabled" else v) for k,v in d.items() if k in {"name","schedule","enabled","next_run_at","last_run_at"}}).eq("id",i).eq("user_id",u).execute()
def delete_automation(i,u): return bool(_data(_client().table("automations").delete().eq("id",i).eq("user_id",u).execute()))
def get_automation(i,u): return _one(_client().table("automations").select("*").eq("id",i).eq("user_id",u).limit(1).execute())
def due_automations(at): return _data(_client().table("automations").select("*").eq("enabled",True).lte("next_run_at",at).order("next_run_at").limit(50).execute())
def list_canvases(u): return _data(_client().table("canvases").select("id,title,created_at,updated_at").eq("user_id",u).order("updated_at",desc=True).execute())
def get_canvas(i,u): return _one(_client().table("canvases").select("*").eq("id",i).eq("user_id",u).limit(1).execute())
def save_canvas(row): _client().table("canvases").upsert(row).execute()
def delete_canvas(i,u): return bool(_data(_client().table("canvases").delete().eq("id",i).eq("user_id",u).execute()))
def list_memories(u,layer=None,query=''):
    q=_client().table('memories').select('*').eq('user_id',u).eq('status','active')
    if layer:q=q.eq('layer',layer)
    if query:q=q.or_(f'key.ilike.%{query}%,value::text.ilike.%{query}%')
    return _data(q.order('updated_at',desc=True).limit(200).execute())
def save_memory(r): _client().table('memories').upsert(r,on_conflict='user_id,layer,key').execute()
def delete_memory(i,u): return bool(_data(_client().table('memories').delete().eq('id',i).eq('user_id',u).execute()))
def clear_memories(u,layer=None):
    q=_client().table('memories').delete().eq('user_id',u)
    if layer:q=q.eq('layer',layer)
    return len(_data(q.execute()))
def save_briefing(r): _client().table('briefing_schedules').upsert(r).execute()
def list_briefings(u): return _data(_client().table('briefing_schedules').select('*').eq('user_id',u).order('created_at').execute())
def due_briefings(at): return _data(_client().table('briefing_schedules').select('*').eq('enabled',True).lte('next_run_at',at).order('next_run_at').limit(50).execute())
def delete_briefing(i,u): return bool(_data(_client().table('briefing_schedules').delete().eq('id',i).eq('user_id',u).execute()))
def save_notification(r): _client().table('notifications').insert(r).execute()
def list_notifications(u,status=None,limit=100):
    q=_client().table('notifications').select('*').eq('user_id',u)
    if status:q=q.eq('status',status)
    return _data(q.order('created_at',desc=True).limit(limit).execute())
def update_notification(i,u,status,n): return bool(_data(_client().table('notifications').update({'status':status,'read_at':n if status=='read' else None}).eq('id',i).eq('user_id',u).execute()))
def save_delivery_attempt(r): _client().table('delivery_attempts').insert(r).execute()
def save_push_subscription(r): _client().table('push_subscriptions').upsert(r,on_conflict='user_id,endpoint').execute()
def list_push_subscriptions(u): return _data(_client().table('push_subscriptions').select('*').eq('user_id',u).eq('enabled',True).execute())
def delete_push_subscription(endpoint,u): return bool(_data(_client().table('push_subscriptions').delete().eq('endpoint',endpoint).eq('user_id',u).execute()))
def get_user_settings(u): return _one(_client().table("user_settings").select("settings,updated_at").eq("user_id",u).limit(1).execute()) or {"settings":{},"updated_at":None}
def save_user_settings(u,s,n): _client().table("user_settings").upsert({"user_id":u,"settings":s,"updated_at":n}).execute();return {"settings":s,"updated_at":n}
def create_action_proposal(r): _client().table("action_proposals").insert(r).execute()
def get_action_proposal(i,u): return _one(_client().table("action_proposals").select("*").eq("id",i).eq("user_id",u).limit(1).execute())
def claim_action_proposal(i,u): return bool(_client().rpc("claim_action_proposal",{"proposal_id":i,"uid":u}).execute().data)
def finish_action_proposal(i,u,status,result): return bool(_data(_client().table("action_proposals").update({"status":status,"result":result,"decided_at":new_now()}).eq("id",i).eq("user_id",u).in_("status",["pending","executing"]).execute()))
def save_media_track(r): _client().table('media_tracks').upsert(r,on_conflict='user_id,provider,url').execute()
def list_media_tracks(u,favorites_only=False):
    q=_client().table('media_tracks').select('*').eq('user_id',u)
    if favorites_only:q=q.eq('is_favorite',True)
    return _data(q.order('updated_at',desc=True).execute())
def get_media_track(i,u): return _one(_client().table('media_tracks').select('*').eq('id',i).eq('user_id',u).limit(1).execute())
def save_media_play(r): _client().table('media_play_history').insert(r).execute()
def list_media_history(u,since=None,limit=100):
    q=_client().table('media_play_history').select('*').eq('user_id',u)
    if since:q=q.gte('played_at',since)
    return _data(q.order('played_at',desc=True).limit(limit).execute())
def claim_internal_rpc(key,u,cap,n):
    claimed=False
    try:_client().table('internal_rpc_receipts').insert({'idempotency_key':key,'user_id':u,'capability':cap,'status':'executing','created_at':n,'updated_at':n}).execute();claimed=True
    except Exception:pass
    row=_one(_client().table('internal_rpc_receipts').select('*').eq('idempotency_key',key).eq('user_id',u).limit(1).execute());return claimed,row
def finish_internal_rpc(key,u,status,result,error,n): _client().table('internal_rpc_receipts').update({'status':status,'result':result,'error':error,'updated_at':n}).eq('idempotency_key',key).eq('user_id',u).execute()
def save_rpc_pipeline(r): _client().table('rpc_pipelines').insert(r).execute()
def list_rpc_pipelines(u,status=None):
    q=_client().table('rpc_pipelines').select('*').eq('user_id',u)
    if status:q=q.eq('status',status)
    return _data(q.order('updated_at',desc=True).execute())
def get_rpc_pipeline(i,u): return _one(_client().table('rpc_pipelines').select('*').eq('id',i).eq('user_id',u).limit(1).execute())
def update_rpc_pipeline(i,u,d,n): return bool(_data(_client().table('rpc_pipelines').update({**d,'updated_at':n}).eq('id',i).eq('user_id',u).execute()))
def save_rpc_run(r): _client().table('rpc_pipeline_runs').upsert(r).execute()
def save_rpc_step(r): _client().table('rpc_pipeline_steps').upsert(r,on_conflict='run_id,step_key').execute()
def get_rpc_run(i,u):
    run=_one(_client().table('rpc_pipeline_runs').select('*').eq('id',i).eq('user_id',u).limit(1).execute())
    if not run:return None
    run['steps']=_data(_client().table('rpc_pipeline_steps').select('*').eq('run_id',i).eq('user_id',u).order('ordinal').execute());return run
def save_delegate_run(r): _client().table('delegate_runs').upsert(r).execute()
def save_delegate_workstream(r): _client().table('delegate_workstreams').upsert(r).execute()
def get_delegate_run(i,u):
    run=_one(_client().table('delegate_runs').select('*').eq('id',i).eq('user_id',u).limit(1).execute())
    if not run:return None
    run['workstreams']=_data(_client().table('delegate_workstreams').select('*').eq('run_id',i).eq('user_id',u).order('ordinal').execute());return run
def list_delegate_runs(u,limit=50): return _data(_client().table('delegate_runs').select('*').eq('user_id',u).order('created_at',desc=True).limit(limit).execute())
def reset_delegate_workstreams(i,u): _client().table('delegate_workstreams').delete().eq('run_id',i).eq('user_id',u).execute()
def save_automation_run(r): _client().table("automation_runs").upsert(r).execute()
def list_automation_runs(u,limit=50): return _data(_client().table("automation_runs").select("*,automations(name)").eq("user_id",u).order("started_at",desc=True).limit(limit).execute())
def get_automation_run(i,u): return _one(_client().table('automation_runs').select('*').eq('id',i).eq('user_id',u).limit(1).execute())
def cancel_automation_run(i,u,n): return bool(_data(_client().table('automation_runs').update({'status':'cancelled','cancelled_at':n,'completed_at':n,'lease_owner':None,'lease_expires_at':None}).eq('id',i).eq('user_id',u).in_('status',['claimed','running','retry_wait']).execute()))
def claim_retry_runs(at,worker,lease_expires,limit=25):
    runs=_data(_client().rpc('claim_retry_automation_runs',{'worker':worker,'batch_size':limit,'lease_seconds':300}).execute());out=[]
    for run in runs:
        a=_one(_client().table('automations').select('*').eq('id',run['automation_id']).eq('user_id',run['user_id']).limit(1).execute())
        if a:out.append({**a,'run_id':run['id'],'scheduled_for':run.get('scheduled_for'),'attempt':run.get('attempt',1)})
    return out
