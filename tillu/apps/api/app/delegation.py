"""Bounded parallel read-only delegates with isolated context and deterministic aggregation."""
from __future__ import annotations
import asyncio,json
from datetime import datetime,timezone
from uuid import uuid4
from .providers import gateway
from .capabilities import registry
from .repository import save_delegate_run,save_delegate_workstream,reset_delegate_workstreams

MAX_DELEGATES=6;MAX_CONCURRENCY=4;MAX_CALLS_PER_DELEGATE=3;TOOL_TIMEOUT=45;MAX_EVIDENCE_CHARS=30000
CANCEL_EVENTS:dict[str,asyncio.Event]={};BACKGROUND_TASKS:dict[str,asyncio.Task]={}

def now():return datetime.now(timezone.utc).isoformat()

def _public_tools():
    return [{'name':x['name'],'description':x['description'],'input_schema':x['input_schema']} for x in registry.catalog('read') if x['name']!='parallel_delegates']

async def plan_delegates(objective:str,count:int)->tuple[list[dict],dict]:
    count=max(2,min(count,MAX_DELEGATES));tools=_public_tools()
    result=await gateway.json_chat([{'role':'system','content':f'Decompose the objective into {count} independent read-only workstreams. Return JSON only: {{"workstreams":[{{"name":"...","objective":"...","tool_calls":[{{"name":"registered tool","args":{{}}}}]}}]}}. Use only supplied tools, at most {MAX_CALLS_PER_DELEGATE} calls per workstream. Never request writes or external effects. Workstreams must not depend on each other.'},{'role':'user','content':json.dumps({'objective':objective,'tools':tools},ensure_ascii=False)[:24000]}],phase='planning',max_tokens=1000)
    if not result:raise RuntimeError('No hosted AI provider is configured')
    available={x['name'] for x in tools};streams=[]
    for raw in result['json'].get('workstreams',[])[:count]:
        calls=[]
        for call in raw.get('tool_calls',[])[:MAX_CALLS_PER_DELEGATE]:
            name=call.get('name')
            if name not in available or not registry.is_read(name):continue
            calls.append({'name':name,'args':call.get('args') if isinstance(call.get('args'),dict) else {}})
        streams.append({'name':str(raw.get('name','Workstream'))[:100],'objective':str(raw.get('objective',''))[:2000],'tool_calls':calls})
    if len(streams)<2:raise ValueError('The objective could not be safely decomposed into independent workstreams')
    return streams,result['route']

async def execute_delegates(user_id:str,objective:str,count:int=3,parent_run_id:str|None=None,run_id:str|None=None)->dict:
    run_id=run_id or str(uuid4());cancel=CANCEL_EVENTS.setdefault(run_id,asyncio.Event());stamp=now();base={'id':run_id,'user_id':user_id,'parent_run_id':parent_run_id,'objective':objective,'status':'planning','plan':{},'result':None,'error':None,'created_at':stamp,'completed_at':None};save_delegate_run(base)
    try:streams,route=await plan_delegates(objective,count)
    except Exception as exc:
        save_delegate_run({**base,'status':'failed','error':f'{type(exc).__name__}: {str(exc)[:300]}','completed_at':now()});raise
    if cancel.is_set():
        save_delegate_run({**base,'status':'cancelled','plan':{'workstreams':streams,'route':route},'completed_at':now()});return {'id':run_id,'status':'cancelled','answer':'Cancelled before execution.','citations':[],'workstreams':[]}
    base.update(status='running',plan={'workstreams':streams,'route':route});save_delegate_run(base);sem=asyncio.Semaphore(MAX_CONCURRENCY)
    async def one(ordinal:int,spec:dict):
        row={'id':str(uuid4()),'run_id':run_id,'user_id':user_id,'ordinal':ordinal,'name':spec['name'],'objective':spec['objective'],'status':'running','tool_calls':spec['tool_calls'],'result':None,'error':None,'started_at':now(),'completed_at':None};save_delegate_workstream(row)
        outputs=[]
        try:
            async with sem:
                for call in spec['tool_calls']:
                    if cancel.is_set():raise asyncio.CancelledError()
                    data=await asyncio.wait_for(registry.execute(call['name'],call['args'],user_id),TOOL_TIMEOUT);outputs.append({'tool':call['name'],'data':data})
            row.update(status='completed',result={'outputs':outputs},completed_at=now());save_delegate_workstream(row);return row
        except asyncio.CancelledError:
            row.update(status='cancelled',result={'outputs':outputs},completed_at=now());save_delegate_workstream(row);return row
        except Exception as exc:
            row.update(status='failed',error=f'{type(exc).__name__}: {str(exc)[:300]}',result={'outputs':outputs},completed_at=now());save_delegate_workstream(row);return row
    rows=await asyncio.gather(*(one(i+1,s) for i,s in enumerate(streams)))
    evidence=[];citations=[];idx=1
    for row in rows:
        for output in (row.get('result') or {}).get('outputs',[]):
            payload=json.dumps(output['data'],ensure_ascii=False,default=str)[:6000];evidence.append(f'[{idx}] {row["name"]} / {output["tool"]}\n{payload}');citations.append({'id':idx,'delegate':row['name'],'tool':output['tool']});idx+=1
    if cancel.is_set():
        result={'answer':'Delegate run cancelled.','citations':citations,'workstreams':[{'id':x['id'],'name':x['name'],'status':x['status'],'error':x.get('error')} for x in rows],'planner':route,'synthesis':None};save_delegate_run({**base,'status':'cancelled','result':result,'completed_at':now()});return {'id':run_id,'status':'cancelled',**result}
    bounded=[];used=0
    for item in evidence:
        if used>=MAX_EVIDENCE_CHARS:break
        bounded.append(item[:MAX_EVIDENCE_CHARS-used]);used+=len(bounded[-1])
    evidence=bounded
    if not evidence:answer='No delegate produced usable evidence.';synthesis_route=None
    else:
        synthesis=await gateway.chat([{'role':'system','content':'Synthesize the isolated delegate evidence into one answer. Cite evidence as [1], [2]. Do not invent facts or imply failed workstreams succeeded.'},{'role':'user','content':f'Objective: {objective}\n\nEvidence:\n'+'\n\n'.join(evidence)}],phase='execution',max_tokens=1200)
        if not synthesis:raise RuntimeError('No hosted AI provider is configured for aggregation')
        answer=synthesis['text'];synthesis_route=synthesis['route']
    status='completed' if any(x['status']=='completed' for x in rows) else 'failed';result={'answer':answer,'citations':citations,'workstreams':[{'id':x['id'],'name':x['name'],'status':x['status'],'error':x.get('error')} for x in rows],'planner':route,'synthesis':synthesis_route};save_delegate_run({**base,'status':status,'result':result,'error':None if status=='completed' else 'All workstreams failed','completed_at':now()});CANCEL_EVENTS.pop(run_id,None);return {'id':run_id,'status':status,**result}

def start_delegate_run(user_id:str,objective:str,count:int,parent_run_id:str|None=None)->str:
    run_id=str(uuid4());stamp=now();save_delegate_run({'id':run_id,'user_id':user_id,'parent_run_id':parent_run_id,'objective':objective,'status':'planning','plan':{},'result':None,'error':None,'created_at':stamp,'completed_at':None});CANCEL_EVENTS[run_id]=asyncio.Event()
    task=asyncio.create_task(execute_delegates(user_id,objective,count,parent_run_id,run_id));BACKGROUND_TASKS[run_id]=task
    task.add_done_callback(lambda _:BACKGROUND_TASKS.pop(run_id,None));return run_id

def restart_delegate_run(row:dict,count:int=3):
    run_id=row['id'];reset_delegate_workstreams(run_id,row['user_id']);CANCEL_EVENTS[run_id]=asyncio.Event();task=asyncio.create_task(execute_delegates(row['user_id'],row['objective'],count,row.get('parent_run_id'),run_id));BACKGROUND_TASKS[run_id]=task;task.add_done_callback(lambda _:BACKGROUND_TASKS.pop(run_id,None))
def cancel_delegate(run_id:str)->bool:
    event=CANCEL_EVENTS.get(run_id)
    if not event:return False
    event.set();return True
