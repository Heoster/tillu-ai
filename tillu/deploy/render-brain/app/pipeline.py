"""Declarative capability RPC pipelines. This module executes no user code."""
from __future__ import annotations
import asyncio,json,re,time
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from .capabilities import registry,validate_action_payload
from .providers import gateway
from .repository import save_rpc_run,save_rpc_step,create_action_proposal,get_action_proposal,get_rpc_run

MAX_STEPS=20;MAX_VALUE_CHARS=20000;MAX_RUN_SECONDS=120;MAX_PARALLEL_READS=4
KEY=re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
def now():return datetime.now(timezone.utc).isoformat()

def validate_definition(definition:dict)->dict:
    if not isinstance(definition,dict) or not isinstance(definition.get('steps'),list):raise ValueError('definition.steps must be a list')
    steps=definition['steps']
    if not 1<=len(steps)<=MAX_STEPS:raise ValueError(f'Pipelines require 1-{MAX_STEPS} steps')
    seen=set()
    for step in steps:
        if not isinstance(step,dict):raise ValueError('Every step must be an object')
        key=step.get('id');cap=step.get('capability')
        if not isinstance(key,str) or not KEY.fullmatch(key) or key in seen:raise ValueError('Step ids must be unique safe identifiers')
        seen.add(key)
        if cap not in registry.tools:raise ValueError(f'Unknown capability: {cap}')
        if not isinstance(step.get('args',{}),dict):raise ValueError('Step args must be an object')
        if step.get('parallel_group') is not None and registry.tools[cap].kind!='read':raise ValueError('Action steps cannot run in parallel groups')
    return {'steps':steps}

def _path(root,path):
    value=root
    for part in path.split('.') if path else []:
        if isinstance(value,dict) and part in value:value=value[part]
        elif isinstance(value,list) and part.isdigit() and int(part)<len(value):value=value[int(part)]
        else:raise ValueError(f'Unresolved pipeline reference: {path}')
    return value

def resolve(value,inputs,outputs):
    if isinstance(value,str) and value.startswith('$input.'):return _path(inputs,value[7:])
    if isinstance(value,str) and value.startswith('$steps.'):
        rest=value[7:];step,_,path=rest.partition('.');return _path(outputs.get(step,{}),path)
    if isinstance(value,dict):return {k:resolve(v,inputs,outputs) for k,v in value.items()}
    if isinstance(value,list):return [resolve(v,inputs,outputs) for v in value]
    return value

def _bounded(value):
    raw=json.dumps(value,ensure_ascii=False,default=str)
    if len(raw)>MAX_VALUE_CHARS:raise ValueError('A pipeline step exceeded the output limit')
    return value

def _run_row(run_id,pipeline,user_id,inputs,status='running'):
    return {'id':run_id,'pipeline_id':pipeline['id'],'user_id':user_id,'status':status,'input':inputs,'output':None,'error':None,'created_at':now(),'completed_at':None}

async def _read_step(run_id,user_id,ordinal,step,args):
    row={'id':str(uuid4()),'run_id':run_id,'user_id':user_id,'ordinal':ordinal,'step_key':step['id'],'capability':step['capability'],'status':'running','result':None,'error':None,'proposal_id':None,'started_at':now(),'completed_at':None};save_rpc_step(row)
    try:
        result=_bounded(await registry.execute(step['capability'],args,user_id));row.update(status='completed',result=result,completed_at=now());save_rpc_step(row);return result
    except Exception as exc:
        row.update(status='failed',error=f'{type(exc).__name__}: {str(exc)[:300]}',completed_at=now());save_rpc_step(row);raise

async def _continue(pipeline,user_id,inputs,run,outputs,start_index=0):
    definition=validate_definition(pipeline['definition']);steps=definition['steps'];deadline=time.monotonic()+MAX_RUN_SECONDS;i=start_index
    try:
        while i<len(steps):
            if run.get('status')=='cancelled':return {'id':run['id'],'status':'cancelled','steps':outputs}
            if time.monotonic()>deadline:raise TimeoutError('Pipeline runtime budget exceeded')
            step=steps[i];group=step.get('parallel_group')
            if group:
                batch=[]
                while i<len(steps) and steps[i].get('parallel_group')==group and len(batch)<MAX_PARALLEL_READS:
                    s=steps[i];batch.append((i+1,s,resolve(s.get('args',{}),inputs,outputs)));i+=1
                results=await asyncio.gather(*(_read_step(run['id'],user_id,o,s,a) for o,s,a in batch))
                for (_,s,_),result in zip(batch,results):outputs[s['id']]=result
                continue
            cap=registry.tools[step['capability']];args=resolve(step.get('args',{}),inputs,outputs)
            if cap.kind=='read':outputs[step['id']]=await _read_step(run['id'],user_id,i+1,step,args);i+=1;continue
            payload=validate_action_payload(cap.name,args)
            if payload is None:raise ValueError(f'Invalid payload for action capability {cap.name}')
            proposal_id=str(uuid4());create_action_proposal({'id':proposal_id,'user_id':user_id,'kind':cap.name,'payload':payload,'status':'pending','created_at':now(),'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()});row={'id':str(uuid4()),'run_id':run['id'],'user_id':user_id,'ordinal':i+1,'step_key':step['id'],'capability':cap.name,'status':'waiting_approval','result':None,'error':None,'proposal_id':proposal_id,'started_at':now(),'completed_at':now()};save_rpc_step(row);run.update(status='waiting_approval',output={'completed':outputs,'proposal_id':proposal_id,'waiting_step':step['id']},completed_at=None);save_rpc_run(run);return {'id':run['id'],**run['output'],'status':'waiting_approval'}
        run.update(status='completed',output={'steps':outputs},completed_at=now());save_rpc_run(run);return {'id':run['id'],'status':'completed','steps':outputs}
    except Exception as exc:
        run.update(status='failed',error=f'{type(exc).__name__}: {str(exc)[:300]}',completed_at=now(),output={'steps':outputs});save_rpc_run(run);raise

async def execute_pipeline(pipeline:dict,user_id:str,inputs:dict)->dict:
    validate_definition(pipeline['definition']);run=_run_row(str(uuid4()),pipeline,user_id,inputs);save_rpc_run(run);return await _continue(pipeline,user_id,inputs,run,{})

async def resume_pipeline(pipeline:dict,user_id:str,run_id:str)->dict:
    stored=get_rpc_run(run_id,user_id)
    if not stored or stored['pipeline_id']!=pipeline['id']:raise KeyError('Pipeline run not found')
    if stored['status']!='waiting_approval':raise ValueError('Pipeline is not waiting for approval')
    waiting=next((x for x in stored['steps'] if x['status']=='waiting_approval'),None)
    if not waiting:raise ValueError('Waiting step is missing')
    proposal=get_action_proposal(waiting['proposal_id'],user_id)
    if not proposal or proposal['status'] not in {'completed','rejected','failed'}:raise ValueError('Action proposal has not been decided')
    if proposal['status']!='completed':
        clean={k:stored.get(k) for k in ('id','pipeline_id','user_id','status','input','output','error','created_at','completed_at')};clean.update(status='failed',error=f"Action was {proposal['status']}",completed_at=now());save_rpc_run(clean);return {'id':run_id,'status':'failed','error':clean['error']}
    outputs={x['step_key']:x['result'] for x in stored['steps'] if x['status']=='completed'};outputs[waiting['step_key']]=proposal.get('result') or {}
    waiting.update(status='completed',result=proposal.get('result') or {},completed_at=now());save_rpc_step(waiting)
    definition=validate_definition(pipeline['definition']);index=next(i for i,x in enumerate(definition['steps']) if x['id']==waiting['step_key'])+1
    run={k:stored.get(k) for k in ('id','pipeline_id','user_id','status','input','output','error','created_at','completed_at')};run.update(status='running',error=None,completed_at=None);save_rpc_run(run);return await _continue(pipeline,user_id,stored['input'],run,outputs,index)

async def draft_pipeline(request:str)->dict:
    tools=[{'name':x['name'],'kind':x['kind'],'description':x['description']} for x in registry.catalog()]
    result=await gateway.json_chat([{'role':'system','content':'Draft a declarative TILLU RPC pipeline. Return JSON only: {"name":"...","description":"...","definition":{"steps":[{"id":"safe-id","capability":"registered","args":{}}]}}. Use only supplied capabilities. Reads may use parallel_group. Never include code, shell, imports, URLs not requested, or approval bypasses.'},{'role':'user','content':json.dumps({'request':request,'capabilities':tools},ensure_ascii=False)[:24000]}],phase='planning',max_tokens=1000)
    if not result:raise RuntimeError('No hosted AI provider is configured')
    data=result['json'];data['definition']=validate_definition(data.get('definition',{}));return data
