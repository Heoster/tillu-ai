"""Closed-loop learning primitives. Generated material is always a draft."""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from uuid import uuid4
from .providers import gateway
from .capabilities import registry
from .repository import conversation_messages,save_summary,search_sessions,save_observation,save_conclusion,list_conclusions,save_skill,list_skills,get_skill,list_skill_outcomes

NAME_RE=re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

def now():return datetime.now(timezone.utc).isoformat()
def allowed_capabilities():return {x['name'] for x in registry.catalog('read')+registry.catalog('action')}

def parse_skill_md(text:str)->dict:
    if not text.startswith('---\n'):raise ValueError('SKILL.md must start with YAML frontmatter')
    end=text.find('\n---\n',4)
    if end<0:raise ValueError('SKILL.md frontmatter is not closed')
    meta={}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        if ':' not in line:raise ValueError('Invalid frontmatter line')
        k,v=line.split(':',1);meta[k.strip()]=v.strip().strip('"\'')
    body=text[end+5:].strip()
    if not meta.get('name') or not meta.get('description'):raise ValueError('name and description are required')
    if not NAME_RE.fullmatch(meta['name']) or len(meta['name'])>64:raise ValueError('name must be a lowercase kebab-case identifier')
    if not body:raise ValueError('Skill instructions are required')
    raw=meta.get('allowed-capabilities','')
    caps=[x.strip() for x in raw.strip('[]').split(',') if x.strip()]
    unknown=set(caps)-allowed_capabilities()
    if unknown:raise ValueError('Unknown capabilities: '+', '.join(sorted(unknown)))
    return {'name':meta['name'],'description':meta['description'],'instructions':body,'allowed_capabilities':caps}

def export_skill_md(skill:dict)->str:
    caps=', '.join(skill.get('allowed_capabilities',[]))
    return f"---\nname: {skill['name']}\ndescription: {skill['description']}\nallowed-capabilities: [{caps}]\n---\n\n{skill['instructions'].strip()}\n"

async def summarize_conversation(user_id:str,conversation_id:str)->dict:
    messages=conversation_messages(conversation_id,user_id)
    if messages is None:raise KeyError('Conversation not found')
    if not messages:raise ValueError('Conversation is empty')
    transcript='\n'.join(f"[{i+1}] {m['role']}: {m['content']}" for i,m in enumerate(messages))
    result=await gateway.json_chat([{'role':'system','content':'Summarize this TILLU session faithfully. Return JSON only: {"summary":"...","topics":["..."]}. Do not infer facts not in the transcript.'},{'role':'user','content':transcript[:24000]}],phase='execution',max_tokens=700)
    if not result:raise RuntimeError('No hosted AI provider is configured')
    data=result['json'];summary=str(data.get('summary','')).strip();topics=[str(x)[:80] for x in data.get('topics',[])[:12]]
    if not summary:raise ValueError('Provider returned an empty summary')
    stamp=now();row={'id':str(uuid4()),'user_id':user_id,'conversation_id':conversation_id,'summary':summary,'topics':topics,'message_count':len(messages),'created_at':stamp,'updated_at':stamp};save_summary(row)
    return {**row,'provider':result['provider'],'model':result['model']}

async def recall(user_id:str,query:str,limit:int=12)->dict:
    hits=search_sessions(user_id,query,max(1,min(limit,30)))
    if not hits:return {'answer':'No matching session evidence was found.','citations':[],'matches':[],'provider':None,'model':None}
    evidence='\n'.join(f"[{i+1}] conversation={h['conversation_id']} at={h['created_at']} role={h['role']}\n{h['content'][:1600]}" for i,h in enumerate(hits))
    result=await gateway.chat([{'role':'system','content':'Answer only from supplied session evidence. Cite claims as [1], [2]. If evidence is insufficient, say so. Never invent personal facts.'},{'role':'user','content':f'Question: {query}\n\nEvidence:\n{evidence}'}],phase='execution',max_tokens=900)
    if not result:raise RuntimeError('No hosted AI provider is configured')
    citations=[{'index':i+1,'conversation_id':h['conversation_id'],'created_at':h['created_at'],'excerpt':h['content'][:320]} for i,h in enumerate(hits)]
    return {'answer':result['text'],'citations':citations,'matches':hits,'provider':result['provider'],'model':result['model']}

async def analyze_session(user_id:str,conversation_id:str)->dict:
    messages=conversation_messages(conversation_id,user_id)
    if messages is None:raise KeyError('Conversation not found')
    transcript='\n'.join(f"[{i+1}] {m['role']}: {m['content']}" for i,m in enumerate(messages))
    result=await gateway.json_chat([{'role':'system','content':'Extract only durable, useful observations explicitly supported by this conversation. Return JSON {"observations":[{"kind":"preference|identity|relationship|project|routine|goal","content":"...","evidence_indexes":[1]}],"conclusions":[{"subject":"Heoster","predicate":"...","value":{},"confidence":0.0,"evidence_indexes":[1]}]}. Avoid sensitive guesses and temporary details.'},{'role':'user','content':transcript[:24000]}],phase='execution',max_tokens=1000)
    if not result:raise RuntimeError('No hosted AI provider is configured')
    stamp=now();observations=[];conclusions=[]
    for item in result['json'].get('observations',[])[:20]:
        indexes=[int(x) for x in item.get('evidence_indexes',[]) if str(x).isdigit() and 1<=int(x)<=len(messages)];evidence=[{'conversation_id':conversation_id,'message_index':x} for x in indexes]
        row={'id':str(uuid4()),'user_id':user_id,'conversation_id':conversation_id,'kind':str(item.get('kind','general'))[:50],'content':str(item.get('content',''))[:1000],'evidence':evidence,'created_at':stamp}
        if row['content'] and evidence:save_observation(row);observations.append(row)
    accepted=list_conclusions(user_id,'accepted')
    for item in result['json'].get('conclusions',[])[:12]:
        indexes=[int(x) for x in item.get('evidence_indexes',[]) if str(x).isdigit() and 1<=int(x)<=len(messages)];evidence=[{'conversation_id':conversation_id,'message_index':x} for x in indexes]
        subject=str(item.get('subject','Heoster'))[:100];predicate=str(item.get('predicate',''))[:100];value=item.get('value',{});conf=max(0,min(1,float(item.get('confidence',0))))
        if not predicate or not evidence:continue
        contradicts=[x['id'] for x in accepted if x['subject']==subject and x['predicate']==predicate and x['value']!=value]
        row={'id':str(uuid4()),'user_id':user_id,'subject':subject,'predicate':predicate,'value':value,'evidence':evidence+([{'contradicts':contradicts}] if contradicts else []),'confidence':conf,'status':'proposed','created_at':stamp,'updated_at':stamp};save_conclusion(row);conclusions.append(row)
    return {'observations':observations,'proposed_conclusions':conclusions,'provider':result['provider'],'model':result['model']}

async def draft_skill(user_id:str,name_hint:str,task:str,capabilities:list[str],source_plan_id:str|None=None,parent_skill_id:str|None=None)->dict:
    unknown=set(capabilities)-allowed_capabilities()
    if unknown:raise ValueError('Unknown capabilities: '+', '.join(sorted(unknown)))
    result=await gateway.json_chat([{'role':'system','content':'Draft a reusable Agent Skill from a successful task. Return JSON only: {"name":"lowercase-kebab-case","description":"...","instructions":"bounded step-by-step instructions"}. Never include shell commands, arbitrary code, credentials, or capabilities not supplied. The skill must preserve approval gates.'},{'role':'user','content':f'Name hint: {name_hint}\nTask and verified outcome:\n{task[:10000]}\nAllowed capabilities: {capabilities}'}],phase='planning',max_tokens=1000)
    if not result:raise RuntimeError('No hosted AI provider is configured')
    data=result['json'];name=str(data.get('name',name_hint)).strip();description=str(data.get('description','')).strip();instructions=str(data.get('instructions','')).strip()
    parsed=parse_skill_md(f'---\nname: {name}\ndescription: {description}\nallowed-capabilities: [{", ".join(capabilities)}]\n---\n\n{instructions}')
    prior=[x for x in list_skills(user_id) if x['name']==name];version=max([x['version'] for x in prior],default=0)+1;stamp=now();row={'id':str(uuid4()),'user_id':user_id,**parsed,'version':version,'status':'draft','source_plan_id':source_plan_id,'parent_skill_id':parent_skill_id,'package_manifest':{},'metrics':{'runs':0,'successes':0,'failures':0},'created_at':stamp,'updated_at':stamp};save_skill(row);return {**row,'provider':result['provider'],'model':result['model']}

async def propose_skill_revision(user_id:str,skill_id:str)->dict:
    skill=get_skill(skill_id,user_id)
    if not skill:raise KeyError('Skill not found')
    outcomes=list_skill_outcomes(user_id,skill_id)
    if len(outcomes)<3:raise ValueError('At least three recorded outcomes are required')
    evidence=json.dumps(outcomes[:20],ensure_ascii=False)
    return await draft_skill(user_id,skill['name'],f"Current instructions:\n{skill['instructions']}\n\nObserved outcomes:\n{evidence}",skill['allowed_capabilities'],skill.get('source_plan_id'),skill_id)
