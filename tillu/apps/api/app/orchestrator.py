"""TILLU's single orchestration runtime.

The graph owns context assembly, tool selection, retrieval, live search, model fallback,
verification, and response formatting. Models can recommend tools, but only this server-side
runtime executes registered tools.
"""
from __future__ import annotations
import json,re,ast,operator
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Any,TypedDict
from langgraph.graph import StateGraph,END
from .providers import gateway
from .sources import sources
from .repository import load_chunks, load_files, list_tasks, list_events, load_progress, list_notes, list_automations, list_automation_runs, get_user_settings, list_memories, list_canvases, list_history, list_sources, load_audit, list_skills, search_sessions, list_conclusions
from .syllabus import SYLLABUS
from .config import settings
from .rag import search_chunks
from .cloud import cloud
from .persona import runtime_context_prompt
from .models import ActionPlan,Risk
from .webreader import read_page
from .communications import gmail
from .capabilities import registry,CapabilitySpec
from .delegation import execute_delegates
from .honcho_adapter import honcho_memory

DOWNLOAD_REQUEST=re.compile(r"\b(download|fetch|collect|get)\b.*\b(pyq|paper|pdf|question)\b",re.I)
def preflight_action_plan(query:str):
    """Deterministic safety gate before the read-only graph; only consequential flows belong here."""
    if not DOWNLOAD_REQUEST.search(query):return None
    plan=ActionPlan(id=str(uuid4()),title='Collect and organise trusted documents',summary='Search trusted sources, validate every PDF, deduplicate it, store it and index it for retrieval.',steps=['Search official and trusted sources','Validate destination and PDF structure','Download with strict size and redirect policy','Deduplicate and store','Index with page citations'],risk=Risk.external,needs_approval=True)
    return {'response':'I prepared a reviewable document-collection plan. Nothing will be downloaded until you approve it.','plan':plan,'ui':{'layout':'approval','components':['ApprovalCard','SourceList','FileGrid']}}

def ToolSpec(name,description,risk,capabilities,handler):
    """Compatibility constructor while handlers remain colocated with the graph."""
    return CapabilitySpec(name,description,risk,capabilities,'read',{'type':'object','additionalProperties':True},handler,False)

async def web_search(args,user_id):return await sources.web_search(args['query'],min(int(args.get('limit',6)),10))
async def webpage_read(args,user_id):
    page=await read_page(args['url']);return {'results':[{'title':page['title'],'url':page['final_url'],'content':page['content'][:30000]}],'provider':'controlled-reader'}
async def gmail_search(args,user_id):
    if not (settings.google_client_id and settings.google_client_secret and settings.gmail_refresh_token):return {'configured':False,'messages':[]}
    return {'configured':True,'messages':await gmail.list(str(args.get('query','')),min(int(args.get('limit',10)),30))}
async def weather(args,user_id):return await sources.weather(float(args.get('latitude',29.97)),float(args.get('longitude',77.55)))
async def news(args,user_id):return await sources.news(args.get('query','India technology education'),min(int(args.get('limit',10)),20))
async def trends(args,user_id):return await sources.hacker_news(min(int(args.get('limit',10)),20))
async def documents(args,user_id):
    hits=search_chunks(args['query'],load_chunks(user_id,args.get('file_id')),min(int(args.get('limit',7)),12))
    return {'provider':'local-document-rag','results':[{'title':h.get('name'),'page':h['page'],'content':h['content'],'score':h['score']} for h in hits]}
async def workspace(args,user_id):
    return {'tasks':list_tasks(user_id)[:20],'events':list_events(user_id)[:20],'progress':load_progress()}
async def notes_context(args,user_id):
    q=args.get('query','').lower();rows=list_notes(user_id);rows=[x for x in rows if not q or q in (x.get('title','')+' '+x.get('content','')).lower()]
    return {'notes':[{'id':x['id'],'title':x['title'],'excerpt':(x.get('content') or '')[:500],'updated_at':x.get('updated_at')} for x in rows[:10]]}
async def automation_context(args,user_id):
    return {'automations':list_automations(user_id)[:20],'recent_runs':list_automation_runs(user_id,10)}
async def files_context(args,user_id):
    q=str(args.get('query','')).lower();rows=load_files(user_id)
    rows=[x for x in rows if not q or q in (x.get('name') or '').lower()]
    return {'files':[{k:v for k,v in x.items() if k not in {'path','storage_path'}} for x in rows[:30]]}
async def research_context(args,user_id):
    q=str(args.get('query','')).lower();rows=list_sources(user_id)
    return {'sources':[x for x in rows if not q or q in ((x.get('title') or '')+' '+(x.get('url') or '')).lower()][:20]}
async def canvas_context(args,user_id):return {'canvases':list_canvases(user_id)[:30]}
async def browser_history_context(args,user_id):return {'history':list_history(user_id,min(int(args.get('limit',30)),100))}
async def settings_context(args,user_id):return get_user_settings(user_id)
async def memory_context(args,user_id):
    rows=list_memories(user_id,args.get('layer'),str(args.get('query','')))
    return {'memories':[{k:v for k,v in x.items() if k not in {'user_id'}} for x in rows[:50]]}
async def session_context(args,user_id):
    query=str(args.get('query',''))[:500];rows=search_sessions(user_id,query,min(max(int(args.get('limit',12)),1),20))
    return {'provider':'private-session-fts','results':[{'title':f"Prior session {x['conversation_id']}",'content':x['content'],'conversation_id':x['conversation_id'],'created_at':x['created_at'],'source':x.get('source','message'),'score':x.get('score')} for x in rows]}
async def user_model_context(args,user_id):
    rows=list_conclusions(user_id,'accepted')
    return {'conclusions':[{k:v for k,v in x.items() if k not in {'user_id'}} for x in rows[:50]]}
async def activity_context(args,user_id):return {'events':load_audit(min(int(args.get('limit',30)),100))}
async def syllabus_context(args,user_id):
    q=args.get('query','').lower();subjects=[]
    for subject in SYLLABUS:
        if not q or q in subject['name'].lower() or any(q in c['name'].lower() for c in subject['chapters']):subjects.append(subject)
    return {'subjects':subjects,'progress':load_progress()}
_ALLOWED_BIN={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
_ALLOWED_UNARY={ast.UAdd:operator.pos,ast.USub:operator.neg}
def _eval_math(node):
    if isinstance(node,ast.Expression):return _eval_math(node.body)
    if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):return node.value
    if isinstance(node,ast.BinOp) and type(node.op) in _ALLOWED_BIN:return _ALLOWED_BIN[type(node.op)](_eval_math(node.left),_eval_math(node.right))
    if isinstance(node,ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:return _ALLOWED_UNARY[type(node.op)](_eval_math(node.operand))
    raise ValueError('Unsupported mathematical expression')
async def calculator(args,user_id):
    expression=str(args.get('expression',''))[:300];value=_eval_math(ast.parse(expression,mode='eval'))
    if abs(float(value))>1e100:raise ValueError('Result is outside safe range')
    return {'expression':expression,'result':value}
async def system_context(args,user_id):
    return {'current_time':datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),'timezone':'Asia/Kolkata','integrations':{'gmail':bool(settings.google_client_id and settings.gmail_refresh_token),'whatsapp':bool(settings.whatsapp_access_token),'browser':True}}
async def parallel_delegates(args,user_id):
    return await execute_delegates(user_id,str(args.get('objective',''))[:5000],min(max(int(args.get('delegates',3)),2),6))
for spec in [
 ToolSpec('parallel_delegates','Run 2-6 isolated read-only workstreams in bounded parallel for complex comparisons or multi-source research','read',['delegation','parallel','research'],parallel_delegates),
 ToolSpec('web_search','Search the current public web with provider fallback','read',['freshness','research'],web_search),
 ToolSpec('webpage_read','Read a specific public webpage through the safe server reader','read',['browser','webpage'],webpage_read),
 ToolSpec('gmail_search','Search and list Gmail when Heoster has configured it','read',['mail','gmail'],gmail_search),
 ToolSpec('weather','Get current weather and forecast','read',['weather'],weather),
 ToolSpec('news','Search recent global news','read',['news'],news),
 ToolSpec('trends','Get current technology trends','read',['trends'],trends),
 ToolSpec('document_search','Search indexed private PDFs with page citations','read',['documents','rag'],documents),
 ToolSpec('workspace_context','Read Heoster’s tasks, events and progress','read',['personal','planning'],workspace),
 ToolSpec('notes_search','Search Heoster’s private notes','read',['notes','memory'],notes_context),
 ToolSpec('automation_context','Inspect configured automations and recent runs','read',['automations','operations'],automation_context),
 ToolSpec('files_context','List and inspect Heoster’s private file library metadata','read',['files','library'],files_context),
 ToolSpec('research_context','List saved research sources','read',['research','sources'],research_context),
 ToolSpec('canvas_context','List persistent canvases','read',['canvas','workspace'],canvas_context),
 ToolSpec('browser_history_context','Read controlled-browser history','read',['browser','history'],browser_history_context),
 ToolSpec('settings_context','Read TILLU preferences and configuration','read',['settings','preferences'],settings_context),
 ToolSpec('memory_context','Recall owner-approved identity, people, preferences, projects, routines and episodic memory','read',['memory','personalization'],memory_context),
 ToolSpec('session_search','Search prior private sessions and summaries with owner-scoped full-text retrieval','read',['memory','sessions','recall'],session_context),
 ToolSpec('user_model_context','Read Heoster-approved evidence-backed user-model conclusions','read',['memory','personalization','user-model'],user_model_context),
 ToolSpec('activity_context','Read recent private audit activity','read',['activity','audit'],activity_context),
 ToolSpec('syllabus_context','Inspect subjects, chapters, topics and learning progress','read',['study','syllabus'],syllabus_context),
 ToolSpec('calculator','Evaluate a bounded arithmetic expression safely','read',['math','calculation'],calculator),
 ToolSpec('system_context','Read current time and optional integration readiness','read',['time','system'],system_context),
]:registry.register(spec)

class AgentState(TypedDict,total=False):
    user_id:str;conversation_id:str;query:str;history:list[dict[str,str]]
    intent:str;selected_tools:list[dict[str,Any]];tool_results:list[dict[str,Any]]
    memory:str;context:str;answer:str;provider:str;model:str;citations:list[dict[str,Any]];errors:list[str]
    widgets:list[dict[str,Any]];generated_at:str;cycle:list[dict[str,Any]];plan_steps:list[str];preferences:dict[str,Any]
    iteration:int;needs_replan:bool;evaluation:dict[str,Any]

FRESH=('latest','today','current','news','weather','trend','recent','price','score','search','who won','this week')
DOC=('pdf','document','file','notes','according to','uploaded','paper')
PERSONAL=('my task','my calendar','my progress','my plan','schedule')

def complexity_score(query:str)->int:
    q=query.lower();score=0
    score+=min(query.count('?'),2);score+=2 if len(query)>500 else 1 if len(query)>250 else 0
    score+=sum(1 for x in ('compare','evaluate','investigate','research','pros and cons','multiple','alternatives','sources') if x in q)
    score+=2 if any(x in q for x in ('in parallel','multiple workstreams','delegate')) else 0
    return score

def route_tools(query:str):
    q=query.lower();out=[]
    url_match=re.search(r'https?://[^\s]+',query)
    if complexity_score(query)>=4 or any(x in q for x in ('in parallel','parallel research','multiple workstreams','delegate this','compare multiple sources')):out.append({'name':'parallel_delegates','args':{'objective':query,'delegates':3}})
    if url_match and any(x in q for x in ('read','open','summarize','analyse','analyze')):out.append({'name':'webpage_read','args':{'url':url_match.group(0)}})
    if any(x in q for x in ('my email','my gmail','mail inbox','find email','search email')):out.append({'name':'gmail_search','args':{'query':query}})
    if 'weather' in q:out.append({'name':'weather','args':{}})
    if any(x in q for x in ('news','headline')):out.append({'name':'news','args':{'query':query}})
    if any(x in q for x in ('trend','trending')):out.append({'name':'trends','args':{}})
    if any(x in q for x in DOC):out.append({'name':'document_search','args':{'query':query}})
    if any(x in q for x in PERSONAL):out.append({'name':'workspace_context','args':{}})
    if any(x in q for x in ('my note','my notes','saved note','find in notes')):out.append({'name':'notes_search','args':{'query':re.sub(r'(?i)(find|search|in|my|notes?)',' ',query).strip()}})
    if any(x in q for x in ('automation','scheduled brief','workflow run')):out.append({'name':'automation_context','args':{}})
    if any(x in q for x in ('my files','file library','uploaded files','my pdf')):out.append({'name':'files_context','args':{'query':query}})
    if any(x in q for x in ('saved research','research sources','saved sources')):out.append({'name':'research_context','args':{'query':query}})
    if any(x in q for x in ('my canvas','my canvases','drawing board')):out.append({'name':'canvas_context','args':{}})
    if any(x in q for x in ('browser history','sites i visited')):out.append({'name':'browser_history_context','args':{}})
    if any(x in q for x in ('my settings','preferences','tillu settings')):out.append({'name':'settings_context','args':{}})
    if any(x in q for x in ('remember about','what do you remember','my friend','what do i like','who am i','my projects','my routine','about me')):out.extend([{'name':'memory_context','args':{'query':''}},{'name':'user_model_context','args':{}}])
    if any(x in q for x in ('earlier conversation','previous session','we discussed','you told me','i told you','last time','before about','recall when')):out.append({'name':'session_search','args':{'query':query,'limit':12}})
    if any(x in q for x in ('activity log','audit log','recent activity')):out.append({'name':'activity_context','args':{}})
    if any(x in q for x in ('syllabus','chapter','topic progress','course progress')):out.append({'name':'syllabus_context','args':{'query':''}})
    math_match=re.search(r'(?i)(?:calculate|compute|what is)\s+([0-9.()\s+*/%^-]+)$',query.strip())
    if math_match:out.append({'name':'calculator','args':{'expression':math_match.group(1).replace('^','**')}})
    if any(x in q for x in ('what time','current time','today date','what date')):out.append({'name':'system_context','args':{}})
    if any(x in q for x in FRESH) and not any(t['name'] in {'weather','news','trends'} for t in out):out.append({'name':'web_search','args':{'query':query}})
    seen=set();unique=[]
    for item in out:
        if item['name'] not in seen:seen.add(item['name']);unique.append(item)
    return unique[:4]

def trim_history(history,max_chars=12000):
    kept=[];used=0
    for m in reversed(history or []):
        text=m.get('content','')
        if used+len(text)>max_chars:break
        kept.append({'role':m.get('role','user'),'content':text});used+=len(text)
    return list(reversed(kept))

async def classify(state:AgentState):
    state['errors']=[];state['cycle']=[];fallback=route_tools(state['query']);prefs=state.get('preferences',{})
    if not prefs.get('auto_fresh_search',True) and not any(x in state['query'].lower() for x in ('search','look up','find online')):fallback=[x for x in fallback if x['name']!='web_search']
    for call in fallback:
        if call['name']=='weather':call['args']={'latitude':prefs.get('default_latitude',settings.default_latitude),'longitude':prefs.get('default_longitude',settings.default_longitude)}
    state['selected_tools']=fallback;state['intent']='tool_augmented' if fallback else 'conversation'
    prompt=[{'role':'system','content':'You are TILLU intent detection. Return JSON only: {"intent":"short_snake_case","complexity":"simple|complex","needs_fresh_data":true|false,"domains":["..."]}. Never answer the request.'},{'role':'user','content':state['query']}]
    try:
        live=await gateway.json_chat(prompt,'intent',220)
        if live:
            d=live['json'];state['intent']=str(d.get('intent') or state['intent'])[:80];state['cycle'].append({'phase':'intent','status':'completed',**live['route'],'intent':state['intent']})
    except Exception as exc:state['errors'].append('intent_router:'+type(exc).__name__);state['cycle'].append({'phase':'intent','status':'fallback','provider':'deterministic','intent':state['intent']})
    if not state['cycle']:state['cycle'].append({'phase':'intent','status':'fallback','provider':'deterministic','intent':state['intent']})
    return state
async def plan_cycle(state:AgentState):
    fallback=state.get('selected_tools',[]);catalog=[{'name':x['name'],'description':x['description']} for x in registry.catalog('read')]
    prompt=[{'role':'system','content':'You are TILLU planner. Build the smallest safe read-only tool plan. Return JSON only: {"steps":["..."],"tool_calls":[{"name":"registered name","args":{}}]}. Use only tools from the supplied catalog. Never propose writes and never answer the user.'},{'role':'user','content':json.dumps({'request':state['query'],'intent':state['intent'],'tools':catalog})}]
    try:
        live=await gateway.json_chat(prompt,'planning',650)
        if live:
            d=live['json'];calls=[]
            for call in d.get('tool_calls',[])[:4]:
                if registry.is_read(call.get('name')) and isinstance(call.get('args',{}),dict):calls.append({'name':call['name'],'args':call.get('args',{})})
            state['selected_tools']=calls or fallback;state['plan_steps']=[str(x)[:300] for x in d.get('steps',[])[:8]];state['cycle'].append({'phase':'planning','status':'completed',**live['route'],'steps':state['plan_steps'],'tools':[x['name'] for x in state['selected_tools']]})
    except Exception as exc:state['errors'].append('planner:'+type(exc).__name__);state['cycle'].append({'phase':'planning','status':'fallback','provider':'deterministic','tools':[x['name'] for x in fallback]})
    if not any(x['phase']=='planning' for x in state['cycle']):state['cycle'].append({'phase':'planning','status':'fallback','provider':'deterministic','tools':[x['name'] for x in fallback]})
    return state
async def retrieve(state:AgentState):
    results=[]
    for call in state.get('selected_tools',[]):
        try:
            operation='search' if call['name'] in {'web_search','news','trends'} else 'tool'
            if not await __import__('asyncio').to_thread(cloud.consume_quota,state['user_id'],call['name'],operation,1,state.get('conversation_id')):raise PermissionError(f'{operation} quota exceeded')
            results.append({'tool':call['name'],'data':await registry.execute(call['name'],call['args'],state['user_id'])})
        except Exception as exc:state['errors'].append(f"{call['name']}:{type(exc).__name__}")
    state['tool_results']=results;state['cycle'].append({'phase':'execution','status':'tools_completed','provider':'tillu-tool-runtime','tools':[x['tool'] for x in results]});return state
async def assemble(state:AgentState):
    sections=[];citations=[];n=1
    if honcho_memory.configured:
        dialectic=await honcho_memory.recall(state['query'],state.get('conversation_id') or None)
        sections.append('Required Honcho dialectic user context:\n'+dialectic)
        state['cycle'].append({'phase':'honcho_recall','status':'completed','provider':'honcho','workspace':settings.honcho_workspace_id})
    elif settings.environment=='production' and settings.honcho_required:raise RuntimeError('Required Honcho memory is unavailable')
    if state.get('preferences',{}).get('memory_capture_enabled',True):
        memories=list_memories(state['user_id'])[:30]
        if memories:sections.append('Owner-approved private memory:\n'+json.dumps([{'layer':x['layer'],'key':x['key'],'value':x['value']} for x in memories],ensure_ascii=False)[:8000])
        conclusions=list_conclusions(state['user_id'],'accepted')[:20]
        if conclusions:sections.append('Heoster-approved evidence-backed user model:\n'+json.dumps([{'subject':x['subject'],'predicate':x['predicate'],'value':x['value'],'confidence':x['confidence']} for x in conclusions],ensure_ascii=False)[:6000])
    query_terms=set(re.findall(r'[a-z0-9]+',state['query'].lower()))
    active=[]
    for skill in list_skills(state['user_id'],'active'):
        discovery=set(re.findall(r'[a-z0-9]+',(skill['name']+' '+skill['description']).lower()))
        if len(query_terms&discovery)>=1:active.append(skill)
    if active:
        sections.append('Approved active skills (instructions are guidance only; all tool calls remain typed and policy-gated):\n'+json.dumps([{'id':x['id'],'name':x['name'],'instructions':x['instructions'],'allowed_capabilities':x['allowed_capabilities']} for x in active[:3]],ensure_ascii=False)[:10000])
        state['cycle'].append({'phase':'skill_activation','status':'completed','skills':[x['name'] for x in active[:3]]})
    for result in state.get('tool_results',[]):
        data=result['data'];rows=data.get('results') or data.get('items') or []
        if rows:
            snippets=[]
            for row in rows[:10]:
                content=(row.get('content') or row.get('title') or '')[:1800];url=row.get('url');page=row.get('page')
                snippets.append(f"[{n}] {row.get('title','Source')}"+(f" page {page}" if page else '')+(f" — {url}" if url else '')+f"\n{content}")
                citations.append({'id':n,'title':row.get('title'),'url':url,'page':page,'tool':result['tool'],'conversation_id':row.get('conversation_id'),'created_at':row.get('created_at'),'source':row.get('source')});n+=1
            sections.append(f"Tool {result['tool']}:\n"+'\n\n'.join(snippets))
        else:sections.append(f"Tool {result['tool']}:\n"+json.dumps(data,ensure_ascii=False)[:8000])
    state['context']='\n\n'.join(sections)[:30000];state['citations']=citations;state['history']=trim_history(state.get('history',[]));return state

async def evaluate_evidence(state:AgentState):
    """Judge whether execution produced enough trustworthy material; never executes writes."""
    iteration=state.get('iteration',0);selected=state.get('selected_tools',[]);results=state.get('tool_results',[])
    def useful(result):
        data=result.get('data') or {};tool=result.get('tool')
        if tool in {'web_search','news','trends','document_search'}:return bool(data.get('results') or data.get('items'))
        if tool=='weather':return bool(data.get('current'))
        if tool=='notes_search':return bool(data.get('notes'))
        if tool=='automation_context':return 'automations' in data
        if tool=='workspace_context':return any(k in data for k in ('tasks','events','progress'))
        return bool(data)
    deterministic_ok=(not selected) or (len(results)==len(selected) and all(useful(r) for r in results))
    evaluation={'sufficient':deterministic_ok,'reason':'tool results available' if deterministic_ok else 'missing or failed tool results','revised_tool_calls':[]}
    if iteration<2 and selected:
        prompt=[{'role':'system','content':'You are TILLU evidence verifier. Return JSON only: {"sufficient":true|false,"reason":"...","revised_tool_calls":[{"name":"registered tool","args":{}}]}. Request another pass only when evidence is missing, stale, contradictory, or a tool failed. Never propose writes.'},{'role':'user','content':json.dumps({'request':state['query'],'plan':state.get('plan_steps',[]),'tools':[x['name'] for x in selected],'results':state.get('context','')[:12000],'errors':state.get('errors',[]),'catalog':[{'name':x['name'],'description':x['description']} for x in registry.catalog('read')]})}]
        try:
            live=await gateway.json_chat(prompt,'planning',500)
            if live:
                raw=live['json'];calls=[]
                for call in raw.get('revised_tool_calls',[])[:4]:
                    if registry.is_read(call.get('name')) and isinstance(call.get('args',{}),dict):calls.append({'name':call['name'],'args':call.get('args',{})})
                evaluation={'sufficient':bool(raw.get('sufficient',False)),'reason':str(raw.get('reason',''))[:500],'revised_tool_calls':calls}
                state['cycle'].append({'phase':'verification','status':'completed',**live['route'],'sufficient':evaluation['sufficient']})
        except Exception as exc:state['errors'].append('evidence_verifier:'+type(exc).__name__)
    state['evaluation']=evaluation;state['needs_replan']=not evaluation['sufficient'] and iteration<2 and bool(evaluation.get('revised_tool_calls') or selected)
    if not any(x.get('phase')=='verification' for x in state['cycle']):state['cycle'].append({'phase':'verification','status':'deterministic','provider':'policy-engine','sufficient':evaluation['sufficient']})
    return state

async def revise_plan(state:AgentState):
    state['iteration']=state.get('iteration',0)+1;calls=state.get('evaluation',{}).get('revised_tool_calls') or state.get('selected_tools',[])
    # Prevent an endless identical retry after the second pass and keep every call registry-bound.
    state['selected_tools']=[x for x in calls if registry.is_read(x.get('name'))][:4]
    state['cycle'].append({'phase':'replan','status':'bounded_retry','provider':'tillu-policy','iteration':state['iteration'],'tools':[x['name'] for x in state['selected_tools']]})
    state['errors']=[];return state

def after_evaluation(state:AgentState):return 'revise' if state.get('needs_replan') else 'respond'

def build_widgets(results:list[dict[str,Any]]):
    widgets=[]
    for result in results:
        tool=result.get('tool');data=result.get('data') or {}
        if tool=='weather' and data.get('current'):
            c=data['current'];widgets.append({'type':'weather','title':'Current conditions','provider':data.get('provider'),'temperature':c.get('temperature_2m'),'feels_like':c.get('apparent_temperature'),'humidity':c.get('relative_humidity_2m'),'wind':c.get('wind_speed_10m'),'weather_code':c.get('weather_code')})
        elif tool in {'news','trends','web_search'}:
            rows=(data.get('results') or data.get('items') or [])[:5]
            if rows:widgets.append({'type':'source_list','title':{'news':'Latest news','trends':'Current trends','web_search':'Live web results'}[tool],'items':[{'title':x.get('title','Result'),'url':x.get('url'),'source':x.get('source') or x.get('domain'),'published_at':x.get('published_at') or x.get('date')} for x in rows]})
        elif tool=='document_search':
            rows=(data.get('results') or [])[:5]
            if rows:widgets.append({'type':'document_hits','title':'Relevant document passages','items':[{'title':x.get('title') or 'Document','page':x.get('page'),'score':round(float(x.get('score',0)),2)} for x in rows]})
        elif tool=='workspace_context':widgets.append({'type':'workspace','title':'Heoster’s workspace','tasks':(data.get('tasks') or [])[:5],'events':(data.get('events') or [])[:5]})
        elif tool=='notes_search':widgets.append({'type':'notes','title':'Matching notes','items':data.get('notes',[])[:6]})
        elif tool=='automation_context':widgets.append({'type':'automations','title':'Automation status','items':data.get('automations',[])[:6],'runs':data.get('recent_runs',[])[:5]})
        elif tool=='syllabus_context':widgets.append({'type':'syllabus','title':'Learning overview','subjects':data.get('subjects',[])[:5]})
        elif tool=='calculator':widgets.append({'type':'calculation','title':'Calculation','expression':data.get('expression'),'result':data.get('result')})
        elif tool=='system_context':widgets.append({'type':'system','title':'Current context','time':data.get('current_time'),'timezone':data.get('timezone'),'integrations':data.get('integrations')})
        elif tool in {'files_context','research_context','canvas_context','browser_history_context','activity_context'}:
            key={'files_context':'files','research_context':'sources','canvas_context':'canvases','browser_history_context':'history','activity_context':'events'}[tool];rows=data.get(key,[])[:8]
            widgets.append({'type':'resource_list','title':{'files_context':'Private files','research_context':'Saved research','canvas_context':'Canvases','browser_history_context':'Browser history','activity_context':'Recent activity'}[tool],'items':[{'id':x.get('id'),'title':x.get('name') or x.get('title') or x.get('action') or x.get('url') or 'Item','detail':x.get('updated_at') or x.get('created_at') or x.get('visited_at') or x.get('risk'),'url':x.get('url')} for x in rows]})
        elif tool=='settings_context':widgets.append({'type':'resource_list','title':'TILLU settings','items':[{'title':k.replace('_',' ').title(),'detail':str(v)} for k,v in (data.get('settings') or {}).items()]})
    return widgets[:4]

async def respond(state:AgentState):
    prefs=state.get('preferences',{});tz_name=prefs.get('timezone','Asia/Kolkata')
    try:tz=ZoneInfo(tz_name)
    except Exception:tz=ZoneInfo('Asia/Kolkata');tz_name='Asia/Kolkata'
    current=datetime.now(tz).strftime('%A, %d %B %Y at %I:%M %p %Z')
    state['generated_at']=datetime.now(tz).isoformat();state['widgets']=build_widgets(state.get('tool_results',[]))
    proactive=' If proactive planning is enabled, suggest at most one useful routine adjustment grounded in approved memory, tasks, or calendar. Never create or change anything without approval.' if prefs.get('proactive_planning_enabled',False) else ''
    messages=[{'role':'system','content':runtime_context_prompt(current,tz_name,prefs.get('response_style','balanced'))+proactive},*state.get('history',[]),{'role':'user','content':state['query']+(f"\n\nVerified tool context:\n{state['context']}" if state.get('context') else '')}]
    if not await __import__('asyncio').to_thread(cloud.consume_quota,state['user_id'],'model-gateway','model',1,state.get('conversation_id')):raise PermissionError('Daily model quota exceeded')
    live=await gateway.chat(messages,phase='execution')
    if live:
        state.update(answer=live['text'],provider=live['provider'],model=live['model']);state['cycle'].append({'phase':'execution','status':'completed',**live['route']})
    else:
        results=state.get('tool_results',[]);answer='No AI provider is configured.'
        if results:
            first=results[0];data=first['data']
            if first['tool']=='weather' and data.get('current'):
                c=data['current'];answer=f"Current weather: {c.get('temperature_2m')}°C, feels like {c.get('apparent_temperature')}°C, humidity {c.get('relative_humidity_2m')}%, wind {c.get('wind_speed_10m')} km/h. Source: {data.get('provider')}."
            elif first['tool']=='calculator':answer=f"**Result:** `{data.get('expression')}` = **{data.get('result')}**"
            elif first['tool']=='system_context':answer=f"The current time is **{datetime.fromisoformat(data['current_time']).strftime('%A, %d %B %Y at %I:%M %p IST')}**."
            elif data.get('results') or data.get('items'):
                rows=(data.get('results') or data.get('items'))[:5];answer='## Results\n'+ '\n'.join(f"- **{x.get('title','Result')}**"+(f" — {x.get('url')}" if x.get('url') else '') for x in rows)
            else:answer='I retrieved the requested personal context. Configure an AI provider for a synthesized interpretation; the verified data is shown below.'
        state.update(answer=answer,provider='orchestrator',model='deterministic-fallback');state['cycle'].append({'phase':'execution','status':'fallback','provider':'deterministic','model':'structured-fallback'})
    
    if state.get('preferences',{}).get('show_agent_cycle',True):state['widgets'].insert(0,{'type':'agent_cycle','title':'TILLU adaptive cycle','phases':state.get('cycle',[])})
    return state
async def verify(state:AgentState):
    # Deterministic post-check: remove citation markers that have no corresponding source.
    valid={str(x['id']) for x in state.get('citations',[])}
    state['answer']=re.sub(r'\[(\d+)\]',lambda m:m.group(0) if m.group(1) in valid else '',state.get('answer',''))
    return state

def build_graph():
    graph=StateGraph(AgentState)
    for name,node in [('classify',classify),('plan',plan_cycle),('retrieve',retrieve),('assemble',assemble),('evaluate',evaluate_evidence),('revise',revise_plan),('respond',respond),('verify',verify)]:graph.add_node(name,node)
    graph.set_entry_point('classify');graph.add_edge('classify','plan');graph.add_edge('plan','retrieve');graph.add_edge('retrieve','assemble');graph.add_edge('assemble','evaluate');graph.add_conditional_edges('evaluate',after_evaluation,{'revise':'revise','respond':'respond'});graph.add_edge('revise','retrieve');graph.add_edge('respond','verify');graph.add_edge('verify',END);return graph.compile()

orchestrator=build_graph()
async def orchestrate(query,user_id,conversation_id='',history=None):
    defaults={'timezone':'Asia/Kolkata','response_style':'balanced','default_latitude':settings.default_latitude,'default_longitude':settings.default_longitude,'show_agent_cycle':True,'auto_fresh_search':True,'notifications_enabled':True}
    preferences=defaults|get_user_settings(user_id).get('settings',{})
    return await orchestrator.ainvoke({'query':query,'user_id':user_id,'conversation_id':conversation_id,'history':history or [],'preferences':preferences,'iteration':0,'needs_replan':False})
