import json,os,re,sqlite3,threading
from pathlib import Path
from datetime import datetime,timezone
DB_PATH=Path(os.environ.get('SQLITE_PATH') or Path(__file__).resolve().parent.parent/'tillu_local.db');_lock=threading.Lock()
def connect():
 db=sqlite3.connect(DB_PATH,check_same_thread=False);db.row_factory=sqlite3.Row;return db
def init_db():
 with _lock,connect() as db:
  db.executescript('''
create table if not exists jobs(id text primary key,kind text,status text,progress integer default 0,payload text default '{}',result text,created_at text,updated_at text);
create table if not exists progress(topic_id text primary key,status text,confidence integer,updated_at text);
create table if not exists audit(id integer primary key autoincrement,action text,risk text,detail text,created_at text);
create table if not exists files(id text primary key,user_id text,name text,path text,mime_type text,size integer,sha256 text,source_url text,created_at text);
create table if not exists document_chunks(id integer primary key autoincrement,file_id text,page integer,content text);
create table if not exists tasks(id text primary key,user_id text,title text,subject text,due_at text,status text default 'todo',priority integer default 2,created_at text);
create table if not exists research_sources(id text primary key,user_id text,url text,title text,content text,created_at text);
create table if not exists calendar_events(id text primary key,user_id text,title text,subject text,start_at text,end_at text,reminder_minutes integer default 15,status text default 'scheduled',created_at text);
create table if not exists agent_checkpoints(run_id text primary key,user_id text,state text,status text,updated_at text);
create table if not exists action_plans(id text primary key,user_id text,run_id text,data text,status text,created_at text);
create table if not exists browser_history(id text primary key,user_id text,url text,title text,visited_at text);
create table if not exists notes(id text primary key,user_id text,title text,content text default '',canvas_data text,tags text default '[]',created_at text,updated_at text);
create table if not exists service_cache(key text primary key,value text,updated_at text);
create table if not exists automations(id text primary key,user_id text,name text,trigger_type text,schedule text,action_type text,config text default '{}',enabled integer default 1,last_run_at text,next_run_at text,created_at text,timezone text not null default 'Asia/Kolkata',retry_policy text not null default '{}',updated_at text);
create table if not exists automation_runs(id text primary key,automation_id text,user_id text,status text,output text,error text,started_at text,completed_at text,scheduled_for text,idempotency_key text,attempt integer not null default 1,lease_owner text,lease_expires_at text,next_attempt_at text,cancelled_at text,unique(user_id,idempotency_key));
create table if not exists conversations(id text primary key,user_id text,title text,created_at text,updated_at text);
create table if not exists messages(id integer primary key autoincrement,conversation_id text,role text,content text,created_at text);
create table if not exists action_proposals(id text primary key,user_id text,kind text,payload text,status text,created_at text,expires_at text,result text);
create table if not exists user_settings(user_id text primary key,settings text not null default '{}',updated_at text);
create table if not exists canvases(id text primary key,user_id text not null,title text not null,data text not null default '',created_at text,updated_at text);
create table if not exists memories(id text primary key,user_id text not null,layer text not null,key text not null,value text not null,sensitivity text not null default 'private',source text not null default 'explicit_chat',confidence real not null default 1,status text not null default 'active',created_at text,updated_at text,last_used_at text,unique(user_id,layer,key));
create table if not exists briefing_schedules(id text primary key,user_id text not null,name text not null,kind text not null,schedule text not null,timezone text not null,channels text not null default '["in_app"]',config text not null default '{}',enabled integer not null default 1,next_run_at text,last_run_at text,created_at text,updated_at text);
create table if not exists notifications(id text primary key,user_id text not null,briefing_id text,kind text not null,title text not null,body text not null,data text not null default '{}',priority text not null default 'normal',status text not null default 'unread',created_at text,read_at text);
create table if not exists delivery_attempts(id text primary key,notification_id text not null,user_id text not null,channel text not null,status text not null,attempt integer not null default 1,error text,external_id text,created_at text,updated_at text);
create table if not exists push_subscriptions(id text primary key,user_id text not null,endpoint text not null,subscription text not null,enabled integer not null default 1,created_at text,updated_at text,unique(user_id,endpoint));
create table if not exists session_summaries(id text primary key,user_id text not null,conversation_id text not null,summary text not null,topics text not null default '[]',message_count integer not null default 0,created_at text,updated_at text,unique(user_id,conversation_id));
create table if not exists user_model_conclusions(id text primary key,user_id text not null,subject text not null,predicate text not null,value text not null,evidence text not null default '[]',confidence real not null,status text not null default 'proposed',created_at text,updated_at text);
create table if not exists nudges(id text primary key,user_id text not null,kind text not null,title text not null,body text not null,evidence text not null default '{}',status text not null default 'pending',due_at text,created_at text);
create table if not exists skills(id text primary key,user_id text not null,name text not null,description text not null,instructions text not null,allowed_capabilities text not null default '[]',version integer not null default 1,status text not null default 'draft',source_plan_id text,parent_skill_id text,package_manifest text not null default '{}',metrics text not null default '{}',created_at text,updated_at text,unique(user_id,name,version));
create table if not exists learning_observations(id text primary key,user_id text not null,conversation_id text,kind text not null,content text not null,evidence text not null default '[]',created_at text);
create table if not exists skill_outcomes(id text primary key,user_id text not null,skill_id text not null,run_id text,success integer not null,score real,evidence text not null default '{}',created_at text);
create virtual table if not exists messages_fts using fts5(conversation_id,role,content,created_at);
create virtual table if not exists summaries_fts using fts5(summary_id,conversation_id,summary,topics);
create table if not exists delegate_runs(id text primary key,user_id text not null,parent_run_id text,objective text not null,status text not null,plan text not null default '{}',result text,error text,created_at text,completed_at text);
create table if not exists delegate_workstreams(id text primary key,run_id text not null,user_id text not null,ordinal integer not null,name text not null,objective text not null,status text not null,tool_calls text not null default '[]',result text,error text,started_at text,completed_at text,unique(run_id,ordinal));
create table if not exists rpc_pipelines(id text primary key,user_id text not null,name text not null,description text not null default '',definition text not null,status text not null default 'draft',version integer not null default 1,created_at text,updated_at text,unique(user_id,name,version));
create table if not exists rpc_pipeline_runs(id text primary key,pipeline_id text not null,user_id text not null,status text not null,input text not null default '{}',output text,error text,created_at text,completed_at text);
create table if not exists rpc_pipeline_steps(id text primary key,run_id text not null,user_id text not null,ordinal integer not null,step_key text not null,capability text not null,status text not null,result text,error text,proposal_id text,started_at text,completed_at text,unique(run_id,step_key));
create table if not exists internal_rpc_receipts(idempotency_key text primary key,user_id text not null,capability text not null,status text not null,result text,error text,created_at text,updated_at text);
create table if not exists media_tracks(id text primary key,user_id text not null,provider text not null,title text not null,artist text,url text not null,is_favorite integer not null default 0,created_at text,updated_at text,unique(user_id,provider,url));
create table if not exists media_play_history(id text primary key,user_id text not null,track_id text,provider text not null,title text not null,artist text,url text not null,played_at text);
''')
  # Forward-compatible local migrations for existing development databases.
  columns={x['name'] for x in db.execute('pragma table_info(conversations)').fetchall()}
  if 'pinned' not in columns:db.execute('alter table conversations add column pinned integer not null default 0')
  if 'archived' not in columns:db.execute('alter table conversations add column archived integer not null default 0')
  message_columns={x['name'] for x in db.execute('pragma table_info(messages)').fetchall()}
  if 'metadata' not in message_columns:db.execute("alter table messages add column metadata text not null default '{}'")
  automation_columns={x['name'] for x in db.execute('pragma table_info(automations)').fetchall()}
  for name,definition in {'timezone':"text not null default 'Asia/Kolkata'",'retry_policy':"text not null default '{}'",'updated_at':'text'}.items():
   if name not in automation_columns:db.execute(f'alter table automations add column {name} {definition}')
  run_columns={x['name'] for x in db.execute('pragma table_info(automation_runs)').fetchall()}
  for name,definition in {'scheduled_for':'text','idempotency_key':'text','attempt':'integer not null default 1','lease_owner':'text','lease_expires_at':'text','next_attempt_at':'text','cancelled_at':'text'}.items():
   if name not in run_columns:db.execute(f'alter table automation_runs add column {name} {definition}')
  db.execute('create unique index if not exists automation_runs_idempotency on automation_runs(user_id,idempotency_key)')
  skill_columns={x['name'] for x in db.execute('pragma table_info(skills)').fetchall()}
  if 'parent_skill_id' not in skill_columns:db.execute('alter table skills add column parent_skill_id text')
  if 'package_manifest' not in skill_columns:db.execute("alter table skills add column package_manifest text not null default '{}'")
  if db.execute('select count(*) from messages_fts').fetchone()[0]==0:db.execute('insert into messages_fts(conversation_id,role,content,created_at) select conversation_id,role,content,created_at from messages')
  if db.execute('select count(*) from summaries_fts').fetchone()[0]==0:db.execute('insert into summaries_fts(summary_id,conversation_id,summary,topics) select id,conversation_id,summary,topics from session_summaries')
  db.commit()
def new_now():return datetime.now(timezone.utc).isoformat()
def save_job(j):
 d=j.model_dump() if hasattr(j,'model_dump') else j;n=d.get('created_at') or new_now()
 with _lock,connect() as db:db.execute("insert into jobs values(?,?,?,?,?,?,?,?) on conflict(id) do update set status=excluded.status,progress=excluded.progress,result=excluded.result,updated_at=excluded.updated_at",(d['id'],d['kind'],d['status'],d.get('progress',0),json.dumps(d.get('payload',{})),json.dumps(d.get('result')) if d.get('result') is not None else None,n,new_now()));db.commit()
def load_jobs():
 with connect() as db:r=db.execute('select * from jobs order by created_at desc').fetchall()
 return [{**dict(x),'payload':json.loads(x['payload']),'result':json.loads(x['result']) if x['result'] else None} for x in r]
def save_progress(i,s,c,n):
 with _lock,connect() as db:db.execute('insert into progress values(?,?,?,?) on conflict(topic_id) do update set status=excluded.status,confidence=excluded.confidence,updated_at=excluded.updated_at',(i,s,c,n));db.commit()
def load_progress():
 with connect() as db:r=db.execute('select * from progress').fetchall()
 return {x['topic_id']:{'status':x['status'],'confidence':x['confidence']} for x in r}
def audit(a,r,d,n):
 with _lock,connect() as db:db.execute('insert into audit(action,risk,detail,created_at) values(?,?,?,?)',(a,r,json.dumps(d),n));db.commit()
def load_audit(limit=50):
 with connect() as db:r=db.execute('select * from audit order by id desc limit ?',(limit,)).fetchall()
 return [{**dict(x),'detail':json.loads(x['detail'])} for x in r]
def save_file(row):
 with _lock,connect() as db:db.execute('insert into files values(:id,:user_id,:name,:path,:mime_type,:size,:sha256,:source_url,:created_at) on conflict(id) do update set name=excluded.name,path=excluded.path',row);db.commit()
def load_files(u):
 with connect() as db:r=db.execute('select * from files where user_id=? order by created_at desc',(u,)).fetchall()
 return [dict(x) for x in r]
def get_file(i,u):
 with connect() as db:r=db.execute('select * from files where id=? and user_id=?',(i,u)).fetchone()
 return dict(r) if r else None
def delete_file(i,u):
 with _lock,connect() as db:
  row=db.execute('select * from files where id=? and user_id=?',(i,u)).fetchone()
  if not row:return None
  db.execute('delete from document_chunks where file_id=?',(i,));db.execute('delete from files where id=? and user_id=?',(i,u));db.commit();return dict(row)
def replace_chunks(i,ch):
 with _lock,connect() as db:db.execute('delete from document_chunks where file_id=?',(i,));db.executemany('insert into document_chunks(file_id,page,content) values(?,?,?)',[(i,x['page'],x['content']) for x in ch]);db.commit()
def load_chunks(u,i=None):
 q='select c.id,c.file_id,c.page,c.content,f.name from document_chunks c join files f on f.id=c.file_id where f.user_id=?';a=[u]
 if i:q+=' and f.id=?';a.append(i)
 with connect() as db:r=db.execute(q,a).fetchall()
 return [dict(x) for x in r]
def create_task(row):
 with _lock,connect() as db:db.execute('insert into tasks values(:id,:user_id,:title,:subject,:due_at,:status,:priority,:created_at)',row);db.commit()
def list_tasks(u):
 with connect() as db:r=db.execute("select * from tasks where user_id=? order by status='done',due_at is null,due_at",(u,)).fetchall()
 return [dict(x) for x in r]
def update_task(i,u,s):
 with _lock,connect() as db:db.execute('update tasks set status=? where id=? and user_id=?',(s,i,u));db.commit()
def patch_task(i,u,d):
 fields=[];args=[]
 for k,v in d.items():
  if k in {'title','subject','due_at','status','priority'}:fields.append(k+'=?');args.append(v)
 if not fields:return False
 with _lock,connect() as db:cur=db.execute('update tasks set '+','.join(fields)+' where id=? and user_id=?',args+[i,u]);db.commit();return cur.rowcount>0
def delete_task(i,u):
 with _lock,connect() as db:cur=db.execute('delete from tasks where id=? and user_id=?',(i,u));db.commit();return cur.rowcount>0
def save_source(row):
 with _lock,connect() as db:db.execute('insert into research_sources values(:id,:user_id,:url,:title,:content,:created_at)',row);db.commit()
def list_sources(u):
 with connect() as db:r=db.execute('select id,url,title,substr(content,1,300) excerpt,created_at from research_sources where user_id=? order by created_at desc',(u,)).fetchall()
 return [dict(x) for x in r]
def delete_source(i,u):
 with _lock,connect() as db:cur=db.execute('delete from research_sources where id=? and user_id=?',(i,u));db.commit();return cur.rowcount>0
def source_chunks(u):
 with connect() as db:r=db.execute('select id,title,content from research_sources where user_id=?',(u,)).fetchall()
 return [{'file':x['title'],'page':1,'content':x['content'][i:i+1400]} for x in r for i in range(0,len(x['content']),1220)]
def create_event(row):
 with _lock,connect() as db:db.execute('insert into calendar_events values(:id,:user_id,:title,:subject,:start_at,:end_at,:reminder_minutes,:status,:created_at)',row);db.commit()
def list_events(u,start=None,end=None):
 q='select * from calendar_events where user_id=?';a=[u]
 if start:q+=' and start_at>=?';a.append(start)
 if end:q+=' and start_at<=?';a.append(end)
 with connect() as db:r=db.execute(q+' order by start_at',a).fetchall()
 return [dict(x) for x in r]
def update_event(i,u,d):
 fields=[];args=[]
 for k,v in d.items():
  if k in {'title','subject','start_at','end_at','reminder_minutes','status'}:fields.append(k+'=?');args.append(v)
 if not fields:return False
 with _lock,connect() as db:cur=db.execute('update calendar_events set '+','.join(fields)+' where id=? and user_id=?',args+[i,u]);db.commit();return cur.rowcount>0
def delete_event(i,u):
 with _lock,connect() as db:cur=db.execute('delete from calendar_events where id=? and user_id=?',(i,u));db.commit();return cur.rowcount>0
def save_checkpoint(i,u,s,status,n):
 with _lock,connect() as db:db.execute('insert into agent_checkpoints values(?,?,?,?,?) on conflict(run_id) do update set state=excluded.state,status=excluded.status,updated_at=excluded.updated_at',(i,u,json.dumps(s),status,n));db.commit()
def load_checkpoint(i,u):
 with connect() as db:r=db.execute('select * from agent_checkpoints where run_id=? and user_id=?',(i,u)).fetchone()
 return {**dict(r),'state':json.loads(r['state'])} if r else None
def save_plan(p,u,run):
 with _lock,connect() as db:db.execute('insert into action_plans values(?,?,?,?,?,?) on conflict(id) do update set data=excluded.data,status=excluded.status',(p['id'],u,run,json.dumps(p),p['status'],new_now()));db.commit()
def get_plan(i):
 with connect() as db:r=db.execute('select * from action_plans where id=?',(i,)).fetchone()
 return {**dict(r),'data':json.loads(r['data'])} if r else None
def claim_plan(i,u):
 with _lock,connect() as db:
  cur=db.execute("update action_plans set status='running' where id=? and user_id=? and status in ('proposed','waiting_approval')",(i,u));db.commit();return cur.rowcount==1
def set_plan_status(i,s):
 with _lock,connect() as db:db.execute('update action_plans set status=? where id=?',(s,i));db.execute('update agent_checkpoints set status=?,updated_at=? where run_id=(select run_id from action_plans where id=?)',(s,new_now(),i));db.commit()
def add_history(r):
 with _lock,connect() as db:db.execute('insert into browser_history values(:id,:user_id,:url,:title,:visited_at)',r);db.commit()
def list_history(u,limit=100):
 with connect() as db:r=db.execute('select * from browser_history where user_id=? order by visited_at desc limit ?',(u,limit)).fetchall()
 return [dict(x) for x in r]
def clear_history(u):
 with _lock,connect() as db:db.execute('delete from browser_history where user_id=?',(u,));db.commit()
def due_reminders(u,at):
 with connect() as db:r=db.execute("select * from calendar_events where user_id=? and status='scheduled' and datetime(start_at,'-'||reminder_minutes||' minutes')<=datetime(?) and datetime(start_at)>=datetime(?)",(u,at,at)).fetchall()
 return [dict(x) for x in r]
def ensure_conversation(i,u,t,n):
 with _lock,connect() as db:
  e=db.execute('select user_id from conversations where id=?',(i,)).fetchone()
  if e and e['user_id']!=u:return False
  db.execute('update conversations set updated_at=? where id=? and user_id=?',(n,i,u)) if e else db.execute('insert into conversations(id,user_id,title,created_at,updated_at) values(?,?,?,?,?)',(i,u,t,n,n));db.commit();return True
def add_message(i,r,c,n,metadata=None):
 with _lock,connect() as db:db.execute('insert into messages(conversation_id,role,content,created_at,metadata) values(?,?,?,?,?)',(i,r,c,n,json.dumps(metadata or {})));db.execute('insert into messages_fts(conversation_id,role,content,created_at) values(?,?,?,?)',(i,r,c,n));db.execute('update conversations set updated_at=? where id=?',(n,i));db.commit()
def list_conversations(u,query='',archived=False):
 q='select c.*,(select content from messages m where m.conversation_id=c.id order by m.id desc limit 1) preview from conversations c where user_id=? and archived=?';args=[u,1 if archived else 0]
 if query:q+=' and (title like ? or exists(select 1 from messages m where m.conversation_id=c.id and m.content like ?))';args.extend([f'%{query}%',f'%{query}%'])
 q+=' order by pinned desc,updated_at desc limit 100'
 with connect() as db:r=db.execute(q,args).fetchall()
 return [dict(x) for x in r]
def update_conversation(i,u,changes):
 allowed={k:v for k,v in changes.items() if k in {'title','pinned','archived'}}
 if not allowed:return False
 fields=','.join(k+'=?' for k in allowed);args=list(allowed.values())+[new_now(),i,u]
 with _lock,connect() as db:cur=db.execute(f'update conversations set {fields},updated_at=? where id=? and user_id=?',args);db.commit();return cur.rowcount>0
def conversation_messages(i,u):
 with connect() as db:
  if not db.execute('select 1 from conversations where id=? and user_id=?',(i,u)).fetchone():return None
  r=db.execute('select role,content,created_at,metadata from messages where conversation_id=? order by id',(i,)).fetchall()
 return [{**dict(x),'metadata':json.loads(x['metadata'] or '{}')} for x in r]
def delete_conversation(i,u):
 with _lock,connect() as db:
  if not db.execute('select 1 from conversations where id=? and user_id=?',(i,u)).fetchone():return False
  db.execute('delete from messages where conversation_id=?',(i,));db.execute('delete from messages_fts where conversation_id=?',(i,));db.execute('delete from conversations where id=?',(i,));db.commit();return True
def search_sessions(u,q,limit=20):
 terms=re.findall(r'[\w-]+',q,flags=re.UNICODE)[:20]
 if not terms:return []
 fts=' OR '.join('"'+x.replace('"','')+'"' for x in terms)
 with connect() as db:
  messages=[{**dict(x),'source':'message'} for x in db.execute("select f.conversation_id,f.role,f.content,f.created_at,bm25(messages_fts) score from messages_fts f join conversations c on c.id=f.conversation_id where messages_fts match ? and c.user_id=? order by score limit ?",(fts,u,limit)).fetchall()]
  summaries=[{'conversation_id':x['conversation_id'],'role':'summary','content':x['content'],'created_at':x['created_at'],'score':x['score'],'source':'summary'} for x in db.execute("select f.conversation_id,f.summary content,s.updated_at created_at,bm25(summaries_fts) score from summaries_fts f join session_summaries s on s.id=f.summary_id where summaries_fts match ? and s.user_id=? order by score limit ?",(fts,u,limit)).fetchall()]
 return sorted(messages+summaries,key=lambda x:x['score'])[:limit]
def save_summary(r):
 row={**r,'topics':json.dumps(r.get('topics',[]))}
 with _lock,connect() as db:
  db.execute('insert into session_summaries values(:id,:user_id,:conversation_id,:summary,:topics,:message_count,:created_at,:updated_at) on conflict(user_id,conversation_id) do update set summary=excluded.summary,topics=excluded.topics,message_count=excluded.message_count,updated_at=excluded.updated_at',row)
  saved=db.execute('select id,conversation_id,summary,topics from session_summaries where user_id=? and conversation_id=?',(r['user_id'],r['conversation_id'])).fetchone();db.execute('delete from summaries_fts where summary_id=?',(saved['id'],));db.execute('insert into summaries_fts values(?,?,?,?)',(saved['id'],saved['conversation_id'],saved['summary'],saved['topics']));db.commit()
def list_summaries(u):
 with connect() as db:r=db.execute('select * from session_summaries where user_id=? order by updated_at desc',(u,)).fetchall()
 return [{**dict(x),'topics':json.loads(x['topics'])} for x in r]
def save_skill(r):
 row={**r,'parent_skill_id':r.get('parent_skill_id'),'package_manifest':json.dumps(r.get('package_manifest',{})),'allowed_capabilities':json.dumps(r.get('allowed_capabilities',[])),'metrics':json.dumps(r.get('metrics',{}))}
 with _lock,connect() as db:db.execute('insert into skills(id,user_id,name,description,instructions,allowed_capabilities,version,status,source_plan_id,parent_skill_id,package_manifest,metrics,created_at,updated_at) values(:id,:user_id,:name,:description,:instructions,:allowed_capabilities,:version,:status,:source_plan_id,:parent_skill_id,:package_manifest,:metrics,:created_at,:updated_at)',row);db.commit()
def list_skills(u,status=None):
 q='select * from skills where user_id=?';args=[u]
 if status:q+=' and status=?';args.append(status)
 with connect() as db:r=db.execute(q+' order by updated_at desc',args).fetchall()
 return [{**dict(x),'allowed_capabilities':json.loads(x['allowed_capabilities']),'package_manifest':json.loads(x['package_manifest'] or '{}'),'metrics':json.loads(x['metrics'])} for x in r]
def update_skill(i,u,d):
 fields=[];args=[]
 for k,v in d.items():
  if k in {'status','description','instructions','metrics'}:fields.append(k+'=?');args.append(json.dumps(v) if k=='metrics' else v)
 if not fields:return False
 with _lock,connect() as db:cur=db.execute('update skills set '+','.join(fields)+',updated_at=? where id=? and user_id=?',args+[new_now(),i,u]);db.commit();return cur.rowcount>0
def get_skill(i,u):
 with connect() as db:r=db.execute('select * from skills where id=? and user_id=?',(i,u)).fetchone()
 return ({**dict(r),'allowed_capabilities':json.loads(r['allowed_capabilities']),'package_manifest':json.loads(r['package_manifest'] or '{}'),'metrics':json.loads(r['metrics'])} if r else None)
def save_conclusion(r):
 row={**r,'value':json.dumps(r['value']),'evidence':json.dumps(r.get('evidence',[]))}
 with _lock,connect() as db:db.execute('insert into user_model_conclusions values(:id,:user_id,:subject,:predicate,:value,:evidence,:confidence,:status,:created_at,:updated_at)',row);db.commit()
def list_conclusions(u,status=None):
 q='select * from user_model_conclusions where user_id=?';a=[u]
 if status:q+=' and status=?';a.append(status)
 with connect() as db:r=db.execute(q+' order by updated_at desc',a).fetchall()
 return [{**dict(x),'value':json.loads(x['value']),'evidence':json.loads(x['evidence'])} for x in r]
def update_conclusion(i,u,d):
 allowed={k:v for k,v in d.items() if k in {'status','confidence','value','evidence'}}
 if not allowed:return False
 fields=[];a=[]
 for k,v in allowed.items():fields.append(k+'=?');a.append(json.dumps(v) if k in {'value','evidence'} else v)
 with _lock,connect() as db:cur=db.execute('update user_model_conclusions set '+','.join(fields)+',updated_at=? where id=? and user_id=?',a+[new_now(),i,u]);db.commit();return cur.rowcount>0
def save_nudge(r):
 row={**r,'evidence':json.dumps(r.get('evidence',{}))}
 with _lock,connect() as db:db.execute('insert into nudges values(:id,:user_id,:kind,:title,:body,:evidence,:status,:due_at,:created_at)',row);db.commit()
def list_nudges(u,status=None):
 q='select * from nudges where user_id=?';a=[u]
 if status:q+=' and status=?';a.append(status)
 with connect() as db:r=db.execute(q+' order by due_at,created_at desc',a).fetchall()
 return [{**dict(x),'evidence':json.loads(x['evidence'])} for x in r]
def update_nudge(i,u,status):
 with _lock,connect() as db:cur=db.execute('update nudges set status=? where id=? and user_id=?',(status,i,u));db.commit();return cur.rowcount>0
def save_observation(r):
 row={**r,'evidence':json.dumps(r.get('evidence',[]))}
 with _lock,connect() as db:db.execute('insert into learning_observations values(:id,:user_id,:conversation_id,:kind,:content,:evidence,:created_at)',row);db.commit()
def list_observations(u,limit=100):
 with connect() as db:r=db.execute('select * from learning_observations where user_id=? order by created_at desc limit ?',(u,limit)).fetchall()
 return [{**dict(x),'evidence':json.loads(x['evidence'])} for x in r]
def save_skill_outcome(r):
 row={**r,'success':1 if r['success'] else 0,'evidence':json.dumps(r.get('evidence',{}))}
 with _lock,connect() as db:db.execute('insert into skill_outcomes values(:id,:user_id,:skill_id,:run_id,:success,:score,:evidence,:created_at)',row);db.commit()
def list_skill_outcomes(u,skill_id):
 with connect() as db:r=db.execute('select * from skill_outcomes where user_id=? and skill_id=? order by created_at desc',(u,skill_id)).fetchall()
 return [{**dict(x),'success':bool(x['success']),'evidence':json.loads(x['evidence'])} for x in r]
def create_note(r):
 with _lock,connect() as db:db.execute('insert into notes values(:id,:user_id,:title,:content,:canvas_data,:tags,:created_at,:updated_at)',r);db.commit()
def list_notes(u):
 with connect() as db:r=db.execute('select * from notes where user_id=? order by updated_at desc',(u,)).fetchall()
 return [dict(x) for x in r]
def get_note(i,u):
 with connect() as db:r=db.execute('select * from notes where id=? and user_id=?',(i,u)).fetchone()
 return dict(r) if r else None
def update_note(i,u,d,n):
 fields=[];a=[]
 for k in ('title','content','canvas_data','tags'):
  if k in d:fields.append(k+'=?');a.append(d[k])
 if fields:
  with _lock,connect() as db:db.execute('update notes set '+','.join(fields)+',updated_at=? where id=? and user_id=?',a+[n,i,u]);db.commit()
 return get_note(i,u)
def delete_note(i,u):
 with _lock,connect() as db:db.execute('delete from notes where id=? and user_id=?',(i,u));db.commit()
def set_cache(k,v,n):
 with _lock,connect() as db:db.execute('insert into service_cache values(?,?,?) on conflict(key) do update set value=excluded.value,updated_at=excluded.updated_at',(k,json.dumps(v),n));db.commit()
def get_cache(k):
 with connect() as db:r=db.execute('select * from service_cache where key=?',(k,)).fetchone()
 return {'value':json.loads(r['value']),'updated_at':r['updated_at']} if r else None
def create_automation(r):
 row={**r,'timezone':r.get('timezone','Asia/Kolkata'),'retry_policy':json.dumps(r.get('retry_policy',{})),'updated_at':r.get('updated_at') or r['created_at']}
 with _lock,connect() as db:db.execute('insert into automations(id,user_id,name,trigger_type,schedule,action_type,config,enabled,last_run_at,next_run_at,created_at,timezone,retry_policy,updated_at) values(:id,:user_id,:name,:trigger_type,:schedule,:action_type,:config,:enabled,:last_run_at,:next_run_at,:created_at,:timezone,:retry_policy,:updated_at)',row);db.commit()
def list_automations(u):
 with connect() as db:r=db.execute('select * from automations where user_id=? order by created_at desc',(u,)).fetchall()
 return [{**dict(x),'config':json.loads(x['config']),'retry_policy':json.loads(x['retry_policy'] or '{}')} for x in r]
def update_automation(i,u,d):
 fields=[];a=[]
 for k,v in d.items():
  if k in {'name','schedule','enabled','next_run_at','last_run_at'}:fields.append(k+'=?');a.append(v)
 if fields:
  with _lock,connect() as db:db.execute('update automations set '+','.join(fields)+' where id=? and user_id=?',a+[i,u]);db.commit()
def delete_automation(i,u):
 with _lock,connect() as db:db.execute('delete from automations where id=? and user_id=?',(i,u));db.commit()
def get_automation(i,u):
 with connect() as db:r=db.execute('select * from automations where id=? and user_id=?',(i,u)).fetchone()
 return {**dict(r),'config':json.loads(r['config']),'retry_policy':json.loads(r['retry_policy'] or '{}')} if r else None
def due_automations(at):
 with connect() as db:r=db.execute("select * from automations where enabled=1 and next_run_at is not null and datetime(next_run_at)<=datetime(?) order by next_run_at limit 50",(at,)).fetchall()
 return [{**dict(x),'config':json.loads(x['config']),'retry_policy':json.loads(x['retry_policy'] or '{}')} for x in r]
def list_canvases(u):
 with connect() as db:r=db.execute('select id,title,created_at,updated_at from canvases where user_id=? order by updated_at desc',(u,)).fetchall()
 return [dict(x) for x in r]
def get_canvas(i,u):
 with connect() as db:r=db.execute('select * from canvases where id=? and user_id=?',(i,u)).fetchone()
 return dict(r) if r else None
def save_canvas(row):
 with _lock,connect() as db:db.execute('insert into canvases(id,user_id,title,data,created_at,updated_at) values(:id,:user_id,:title,:data,:created_at,:updated_at) on conflict(id) do update set title=excluded.title,data=excluded.data,updated_at=excluded.updated_at where user_id=excluded.user_id',row);db.commit()
def delete_canvas(i,u):
 with _lock,connect() as db:cur=db.execute('delete from canvases where id=? and user_id=?',(i,u));db.commit();return cur.rowcount>0
def list_memories(u,layer=None,query=''):
 q="select * from memories where user_id=? and status='active'";args=[u]
 if layer:q+=' and layer=?';args.append(layer)
 if query:q+=' and (key like ? or value like ?)';args.extend([f'%{query}%',f'%{query}%'])
 with connect() as db:r=db.execute(q+' order by updated_at desc limit 200',args).fetchall()
 return [{**dict(x),'value':json.loads(x['value'])} for x in r]
def save_memory(r):
 row={**r,'value':json.dumps(r['value'])}
 with _lock,connect() as db:db.execute('insert into memories values(:id,:user_id,:layer,:key,:value,:sensitivity,:source,:confidence,:status,:created_at,:updated_at,:last_used_at) on conflict(user_id,layer,key) do update set value=excluded.value,sensitivity=excluded.sensitivity,source=excluded.source,confidence=excluded.confidence,status=excluded.status,updated_at=excluded.updated_at',row);db.commit()
def delete_memory(i,u):
 with _lock,connect() as db:cur=db.execute('delete from memories where id=? and user_id=?',(i,u));db.commit();return cur.rowcount>0
def clear_memories(u,layer=None):
 with _lock,connect() as db:
  cur=db.execute('delete from memories where user_id=? and layer=?',(u,layer)) if layer else db.execute('delete from memories where user_id=?',(u,));db.commit();return cur.rowcount
def save_briefing(r):
 row={**r,'channels':json.dumps(r.get('channels',['in_app'])),'config':json.dumps(r.get('config',{}))}
 with _lock,connect() as db:db.execute('insert into briefing_schedules values(:id,:user_id,:name,:kind,:schedule,:timezone,:channels,:config,:enabled,:next_run_at,:last_run_at,:created_at,:updated_at) on conflict(id) do update set name=excluded.name,schedule=excluded.schedule,timezone=excluded.timezone,channels=excluded.channels,config=excluded.config,enabled=excluded.enabled,next_run_at=excluded.next_run_at,last_run_at=excluded.last_run_at,updated_at=excluded.updated_at',row);db.commit()
def list_briefings(u):
 with connect() as db:r=db.execute('select * from briefing_schedules where user_id=? order by created_at',(u,)).fetchall()
 return [{**dict(x),'channels':json.loads(x['channels']),'config':json.loads(x['config']),'enabled':bool(x['enabled'])} for x in r]
def due_briefings(at):
 with connect() as db:r=db.execute('select * from briefing_schedules where enabled=1 and next_run_at is not null and datetime(next_run_at)<=datetime(?) order by next_run_at limit 50',(at,)).fetchall()
 return [{**dict(x),'channels':json.loads(x['channels']),'config':json.loads(x['config'])} for x in r]
def delete_briefing(i,u):
 with _lock,connect() as db:cur=db.execute('delete from briefing_schedules where id=? and user_id=?',(i,u));db.commit();return cur.rowcount>0
def save_notification(r):
 row={**r,'data':json.dumps(r.get('data',{}))}
 with _lock,connect() as db:db.execute('insert into notifications values(:id,:user_id,:briefing_id,:kind,:title,:body,:data,:priority,:status,:created_at,:read_at)',row);db.commit()
def list_notifications(u,status=None,limit=100):
 q='select * from notifications where user_id=?';args=[u]
 if status:q+=' and status=?';args.append(status)
 with connect() as db:r=db.execute(q+' order by created_at desc limit ?',args+[limit]).fetchall()
 return [{**dict(x),'data':json.loads(x['data'])} for x in r]
def update_notification(i,u,status,n):
 with _lock,connect() as db:cur=db.execute('update notifications set status=?,read_at=? where id=? and user_id=?',(status,n if status=='read' else None,i,u));db.commit();return cur.rowcount>0
def save_delivery_attempt(r):
 with _lock,connect() as db:db.execute('insert into delivery_attempts values(:id,:notification_id,:user_id,:channel,:status,:attempt,:error,:external_id,:created_at,:updated_at)',r);db.commit()
def save_push_subscription(r):
 row={**r,'subscription':json.dumps(r['subscription'])}
 with _lock,connect() as db:db.execute('insert into push_subscriptions values(:id,:user_id,:endpoint,:subscription,:enabled,:created_at,:updated_at) on conflict(user_id,endpoint) do update set subscription=excluded.subscription,enabled=1,updated_at=excluded.updated_at',row);db.commit()
def list_push_subscriptions(u):
 with connect() as db:r=db.execute('select * from push_subscriptions where user_id=? and enabled=1',(u,)).fetchall()
 return [{**dict(x),'subscription':json.loads(x['subscription'])} for x in r]
def delete_push_subscription(endpoint,u):
 with _lock,connect() as db:cur=db.execute('delete from push_subscriptions where endpoint=? and user_id=?',(endpoint,u));db.commit();return cur.rowcount>0
def get_user_settings(u):
 with connect() as db:r=db.execute('select settings,updated_at from user_settings where user_id=?',(u,)).fetchone()
 return {'settings':json.loads(r['settings']),'updated_at':r['updated_at']} if r else {'settings':{},'updated_at':None}
def save_user_settings(u,s,n):
 with _lock,connect() as db:db.execute('insert into user_settings(user_id,settings,updated_at) values(?,?,?) on conflict(user_id) do update set settings=excluded.settings,updated_at=excluded.updated_at',(u,json.dumps(s),n));db.commit()
 return {'settings':s,'updated_at':n}
def create_action_proposal(r):
 row={**r,'payload':json.dumps(r['payload']),'result':None}
 with _lock,connect() as db:db.execute('insert into action_proposals values(:id,:user_id,:kind,:payload,:status,:created_at,:expires_at,:result)',row);db.commit()
def get_action_proposal(i,u):
 with connect() as db:r=db.execute('select * from action_proposals where id=? and user_id=?',(i,u)).fetchone()
 return {**dict(r),'payload':json.loads(r['payload']),'result':json.loads(r['result']) if r['result'] else None} if r else None
def claim_action_proposal(i,u):
 with _lock,connect() as db:
  cur=db.execute("update action_proposals set status='executing' where id=? and user_id=? and status='pending'",(i,u));db.commit();return cur.rowcount==1
def finish_action_proposal(i,u,status,result):
 with _lock,connect() as db:
  cur=db.execute("update action_proposals set status=?,result=? where id=? and user_id=? and status in ('pending','executing')",(status,json.dumps(result),i,u));db.commit();return cur.rowcount==1
def save_media_track(r):
 row={**r,'is_favorite':1 if r.get('is_favorite') else 0}
 with _lock,connect() as db:db.execute('insert into media_tracks values(:id,:user_id,:provider,:title,:artist,:url,:is_favorite,:created_at,:updated_at) on conflict(user_id,provider,url) do update set title=excluded.title,artist=excluded.artist,is_favorite=excluded.is_favorite,updated_at=excluded.updated_at',row);db.commit()
def list_media_tracks(u,favorites_only=False):
 q='select * from media_tracks where user_id=?';a=[u]
 if favorites_only:q+=' and is_favorite=1'
 with connect() as db:r=db.execute(q+' order by updated_at desc',a).fetchall()
 return [{**dict(x),'is_favorite':bool(x['is_favorite'])} for x in r]
def get_media_track(i,u):
 with connect() as db:r=db.execute('select * from media_tracks where id=? and user_id=?',(i,u)).fetchone()
 return ({**dict(r),'is_favorite':bool(r['is_favorite'])} if r else None)
def save_media_play(r):
 with _lock,connect() as db:db.execute('insert into media_play_history values(:id,:user_id,:track_id,:provider,:title,:artist,:url,:played_at)',r);db.commit()
def list_media_history(u,since=None,limit=100):
 q='select * from media_play_history where user_id=?';a=[u]
 if since:q+=' and played_at>=?';a.append(since)
 with connect() as db:r=db.execute(q+' order by played_at desc limit ?',a+[limit]).fetchall()
 return [dict(x) for x in r]
def claim_internal_rpc(key,u,cap,n):
 with _lock,connect() as db:
  cur=db.execute("insert or ignore into internal_rpc_receipts values(?,?,?,'executing',null,null,?,?)",(key,u,cap,n,n));db.commit()
  row=db.execute('select * from internal_rpc_receipts where idempotency_key=? and user_id=?',(key,u)).fetchone();return cur.rowcount==1,({**dict(row),'result':json.loads(row['result']) if row['result'] else None} if row else None)
def finish_internal_rpc(key,u,status,result,error,n):
 with _lock,connect() as db:db.execute('update internal_rpc_receipts set status=?,result=?,error=?,updated_at=? where idempotency_key=? and user_id=?',(status,json.dumps(result) if result is not None else None,error,n,key,u));db.commit()
def save_rpc_pipeline(r):
 row={**r,'definition':json.dumps(r['definition'])}
 with _lock,connect() as db:db.execute('insert into rpc_pipelines values(:id,:user_id,:name,:description,:definition,:status,:version,:created_at,:updated_at)',row);db.commit()
def list_rpc_pipelines(u,status=None):
 q='select * from rpc_pipelines where user_id=?';a=[u]
 if status:q+=' and status=?';a.append(status)
 with connect() as db:r=db.execute(q+' order by updated_at desc',a).fetchall()
 return [{**dict(x),'definition':json.loads(x['definition'])} for x in r]
def get_rpc_pipeline(i,u):
 with connect() as db:r=db.execute('select * from rpc_pipelines where id=? and user_id=?',(i,u)).fetchone()
 return {**dict(r),'definition':json.loads(r['definition'])} if r else None
def update_rpc_pipeline(i,u,d,n):
 allowed={k:(json.dumps(v) if k=='definition' else v) for k,v in d.items() if k in {'status','description','definition'}}
 if not allowed:return False
 with _lock,connect() as db:cur=db.execute('update rpc_pipelines set '+','.join(k+'=?' for k in allowed)+',updated_at=? where id=? and user_id=?',list(allowed.values())+[n,i,u]);db.commit();return cur.rowcount>0
def save_rpc_run(r):
 row={**r,'input':json.dumps(r.get('input',{})),'output':json.dumps(r['output']) if r.get('output') is not None else None}
 with _lock,connect() as db:db.execute('insert into rpc_pipeline_runs values(:id,:pipeline_id,:user_id,:status,:input,:output,:error,:created_at,:completed_at) on conflict(id) do update set status=excluded.status,output=excluded.output,error=excluded.error,completed_at=excluded.completed_at',row);db.commit()
def save_rpc_step(r):
 row={**r,'result':json.dumps(r['result']) if r.get('result') is not None else None}
 with _lock,connect() as db:db.execute('insert into rpc_pipeline_steps values(:id,:run_id,:user_id,:ordinal,:step_key,:capability,:status,:result,:error,:proposal_id,:started_at,:completed_at) on conflict(run_id,step_key) do update set status=excluded.status,result=excluded.result,error=excluded.error,proposal_id=excluded.proposal_id,completed_at=excluded.completed_at',row);db.commit()
def get_rpc_run(i,u):
 with connect() as db:
  run=db.execute('select * from rpc_pipeline_runs where id=? and user_id=?',(i,u)).fetchone()
  if not run:return None
  steps=db.execute('select * from rpc_pipeline_steps where run_id=? and user_id=? order by ordinal',(i,u)).fetchall()
 return {**dict(run),'input':json.loads(run['input']),'output':json.loads(run['output']) if run['output'] else None,'steps':[{**dict(x),'result':json.loads(x['result']) if x['result'] else None} for x in steps]}
def save_delegate_run(r):
 row={**r,'plan':json.dumps(r.get('plan',{})),'result':json.dumps(r['result']) if r.get('result') is not None else None}
 with _lock,connect() as db:db.execute('insert into delegate_runs values(:id,:user_id,:parent_run_id,:objective,:status,:plan,:result,:error,:created_at,:completed_at) on conflict(id) do update set status=excluded.status,plan=excluded.plan,result=excluded.result,error=excluded.error,completed_at=excluded.completed_at',row);db.commit()
def save_delegate_workstream(r):
 row={**r,'tool_calls':json.dumps(r.get('tool_calls',[])),'result':json.dumps(r['result']) if r.get('result') is not None else None}
 with _lock,connect() as db:db.execute('insert into delegate_workstreams values(:id,:run_id,:user_id,:ordinal,:name,:objective,:status,:tool_calls,:result,:error,:started_at,:completed_at) on conflict(id) do update set status=excluded.status,tool_calls=excluded.tool_calls,result=excluded.result,error=excluded.error,started_at=excluded.started_at,completed_at=excluded.completed_at',row);db.commit()
def get_delegate_run(i,u):
 with connect() as db:
  run=db.execute('select * from delegate_runs where id=? and user_id=?',(i,u)).fetchone()
  if not run:return None
  streams=db.execute('select * from delegate_workstreams where run_id=? and user_id=? order by ordinal',(i,u)).fetchall()
 def decode(x):return {**dict(x),'plan':json.loads(x['plan'] or '{}'),'result':json.loads(x['result']) if x['result'] else None}
 return {**decode(run),'workstreams':[{**dict(x),'tool_calls':json.loads(x['tool_calls'] or '[]'),'result':json.loads(x['result']) if x['result'] else None} for x in streams]}
def list_delegate_runs(u,limit=50):
 with connect() as db:r=db.execute('select * from delegate_runs where user_id=? order by created_at desc limit ?',(u,limit)).fetchall()
 return [{**dict(x),'plan':json.loads(x['plan'] or '{}'),'result':json.loads(x['result']) if x['result'] else None} for x in r]
def reset_delegate_workstreams(i,u):
 with _lock,connect() as db:db.execute('delete from delegate_workstreams where run_id=? and user_id=?',(i,u));db.commit()
def save_automation_run(r):
 row={**r,'scheduled_for':r.get('scheduled_for'),'idempotency_key':r.get('idempotency_key'),'attempt':r.get('attempt',1),'lease_owner':r.get('lease_owner'),'lease_expires_at':r.get('lease_expires_at'),'next_attempt_at':r.get('next_attempt_at'),'cancelled_at':r.get('cancelled_at')}
 with _lock,connect() as db:db.execute('insert into automation_runs(id,automation_id,user_id,status,output,error,started_at,completed_at,scheduled_for,idempotency_key,attempt,lease_owner,lease_expires_at,next_attempt_at,cancelled_at) values(:id,:automation_id,:user_id,:status,:output,:error,:started_at,:completed_at,:scheduled_for,:idempotency_key,:attempt,:lease_owner,:lease_expires_at,:next_attempt_at,:cancelled_at) on conflict(id) do update set status=excluded.status,output=excluded.output,error=excluded.error,completed_at=excluded.completed_at,next_attempt_at=excluded.next_attempt_at,lease_owner=excluded.lease_owner,lease_expires_at=excluded.lease_expires_at,cancelled_at=excluded.cancelled_at',row);db.commit()
def claim_due_automations(at,worker,lease_expires,limit=25):
 claimed=[]
 with _lock,connect() as db:
  db.execute('begin immediate')
  rows=db.execute('select * from automations where enabled=1 and next_run_at is not null and datetime(next_run_at)<=datetime(?) order by next_run_at limit ?',(at,limit)).fetchall()
  for x in rows:
   key=x['id']+':'+x['next_run_at'];rid=str(__import__('uuid').uuid4())
   cur=db.execute("insert or ignore into automation_runs(id,automation_id,user_id,status,started_at,scheduled_for,idempotency_key,attempt,lease_owner,lease_expires_at) values(?,?,?,'claimed',?,?,?,?,?,?)",(rid,x['id'],x['user_id'],at,x['next_run_at'],key,1,worker,lease_expires))
   if cur.rowcount:claimed.append({**dict(x),'config':json.loads(x['config']),'retry_policy':json.loads(x['retry_policy'] or '{}'),'run_id':rid,'scheduled_for':x['next_run_at']})
  db.commit()
 return claimed
def list_automation_runs(u,limit=50):
 with connect() as db:r=db.execute('select r.*,a.name from automation_runs r join automations a on a.id=r.automation_id where r.user_id=? order by r.started_at desc limit ?',(u,limit)).fetchall()
 return [dict(x) for x in r]
def get_automation_run(i,u):
 with connect() as db:r=db.execute('select * from automation_runs where id=? and user_id=?',(i,u)).fetchone()
 return dict(r) if r else None
def cancel_automation_run(i,u,n):
 with _lock,connect() as db:cur=db.execute("update automation_runs set status='cancelled',cancelled_at=?,completed_at=?,lease_owner=null,lease_expires_at=null where id=? and user_id=? and status in ('claimed','running','retry_wait')",(n,n,i,u));db.commit();return cur.rowcount>0
def claim_retry_runs(at,worker,lease_expires,limit=25):
 claimed=[]
 with _lock,connect() as db:
  db.execute('begin immediate')
  rows=db.execute("select r.*,a.name,a.trigger_type,a.schedule,a.action_type,a.config,a.enabled,a.last_run_at,a.next_run_at,a.created_at automation_created_at,a.timezone,a.retry_policy,a.updated_at from automation_runs r join automations a on a.id=r.automation_id where a.enabled=1 and r.status in ('retry_wait','claimed','running') and ((r.status='retry_wait' and datetime(r.next_attempt_at)<=datetime(?)) or (r.status in ('claimed','running') and datetime(r.lease_expires_at)<=datetime(?))) order by coalesce(r.next_attempt_at,r.lease_expires_at) limit ?",(at,at,limit)).fetchall()
  for x in rows:
   cur=db.execute("update automation_runs set status='claimed',attempt=attempt+1,lease_owner=?,lease_expires_at=?,started_at=?,error=null where id=? and status in ('retry_wait','claimed','running')",(worker,lease_expires,at,x['id']))
   if cur.rowcount:claimed.append({**dict(x),'id':x['automation_id'],'run_id':x['id'],'config':json.loads(x['config']),'retry_policy':json.loads(x['retry_policy'] or '{}'),'attempt':x['attempt']+1})
  db.commit()
 return claimed
