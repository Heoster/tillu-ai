"""Single typed capability registry for every TILLU-owned read and action tool.

Read handlers are registered by the orchestrator. Action schemas are registered here
and executed only by the approval service/API. This module is the canonical catalog
used by models, API discovery, tests, and later UI generation.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any,Awaitable,Callable,Literal

ToolFn=Callable[[dict[str,Any],str],Awaitable[dict[str,Any]]]
CapabilityKind=Literal['read','action']

@dataclass
class CapabilitySpec:
    name:str
    description:str
    risk:str
    capabilities:list[str]
    kind:CapabilityKind
    input_schema:dict[str,Any]
    handler:ToolFn|None=None
    approval_required:bool=False
    configured:bool=True
    def public(self):
        value=asdict(self);value.pop('handler',None);return value

class CapabilityRegistry:
    def __init__(self):self.tools:dict[str,CapabilitySpec]={}
    def register(self,spec:CapabilitySpec):self.tools[spec.name]=spec
    def register_read(self,name:str,description:str,capabilities:list[str],handler:ToolFn,input_schema:dict[str,Any]|None=None):
        self.tools[name]=CapabilitySpec(name,description,'read',capabilities,'read',input_schema or {'type':'object','additionalProperties':True},handler,False)
    def register_action(self,name:str,description:str,schema:dict[str,Any],capabilities:list[str]|None=None,risk:str='write'):
        self.tools[name]=CapabilitySpec(name,description,risk,capabilities or ['write'],'action',schema,None,True)
    def catalog(self,kind:CapabilityKind|None=None):return [x.public() for x in self.tools.values() if kind is None or x.kind==kind]
    def is_read(self,name:str)->bool:return bool(name in self.tools and self.tools[name].kind=='read')
    async def execute(self,name,args,user_id):
        tool=self.tools.get(name)
        if not tool:raise ValueError(f'Unknown capability: {name}')
        if tool.kind!='read' or tool.risk!='read' or not tool.handler:raise PermissionError('Action capabilities require a persisted approval')
        return await tool.handler(args,user_id)

registry=CapabilityRegistry()

ACTION_SCHEMAS={
 'create_task':{'required':['title'],'allowed':['title','subject','due_at','priority']},
 'update_task':{'required':['id'],'allowed':['id','title','subject','due_at','status','priority']},'delete_task':{'required':['id'],'allowed':['id']},
 'create_note':{'required':['title'],'allowed':['title','content','tags']},'update_note':{'required':['id'],'allowed':['id','title','content','tags']},'delete_note':{'required':['id'],'allowed':['id']},
 'create_canvas':{'required':['title'],'allowed':['title']},'update_canvas':{'required':['id'],'allowed':['id','title','clear']},'delete_canvas':{'required':['id'],'allowed':['id']},
 'create_event':{'required':['title','start_at'],'allowed':['title','subject','start_at','end_at','reminder_minutes']},
 'update_event':{'required':['id'],'allowed':['id','title','subject','start_at','end_at','reminder_minutes','status']},'delete_event':{'required':['id'],'allowed':['id']},
 'create_automation':{'required':['name','action_type'],'allowed':['name','trigger_type','schedule','action_type','config','enabled','next_run_at']},
 'update_automation':{'required':['id'],'allowed':['id','name','schedule','enabled']},'delete_automation':{'required':['id'],'allowed':['id']},'run_automation':{'required':['id'],'allowed':['id']},'automation_backup':{'required':['automation_id','scheduled_for'],'allowed':['automation_id','scheduled_for']},
 'media_play':{'required':['title','url'],'allowed':['track_id','provider','title','artist','url']},'media_favorite':{'required':['title','url'],'allowed':['track_id','provider','title','artist','url','favorite']},
 'update_progress':{'required':['topic_id','status','confidence'],'allowed':['topic_id','status','confidence']},
 'save_research_source':{'required':['url'],'allowed':['url']},'delete_source':{'required':['id'],'allowed':['id']},
 'delete_file':{'required':['id'],'allowed':['id']},'index_file':{'required':['id'],'allowed':['id']},
 'clear_browser_history':{'required':[],'allowed':[]},
 'browser_start':{'required':[],'allowed':[]},'browser_navigate':{'required':['session_id','url'],'allowed':['session_id','url']},
 'browser_action':{'required':['session_id','action','selector'],'allowed':['session_id','action','selector','text','key']},
 'gmail_draft':{'required':['to','subject','body'],'allowed':['to','subject','body','thread_id']},
 'whatsapp_send':{'required':['to','body'],'allowed':['to','body']},
 'create_memory':{'required':['layer','key','value'],'allowed':['layer','key','value','sensitivity','source','confidence']},'delete_memory':{'required':['id'],'allowed':['id']},'clear_memories':{'required':[],'allowed':['layer']},
 'update_settings':{'required':[],'allowed':['timezone','response_style','default_latitude','default_longitude','show_agent_cycle','auto_fresh_search','notifications_enabled','memory_capture_enabled','proactive_planning_enabled','activity_tracking_enabled']}
}
ACTION_LABELS={name:name.replace('_',' ').title() for name in ACTION_SCHEMAS}
ACTION_LABELS.update({'create_note':'Save note','create_event':'Create calendar event','update_event':'Update calendar event','gmail_draft':'Create Gmail draft','browser_start':'Start controlled browser','browser_navigate':'Navigate controlled browser','browser_action':'Control browser','save_research_source':'Save research source'})
_EXTERNAL={'whatsapp_send','gmail_draft','browser_action','browser_navigate','save_research_source','media_play'}
for _name,_shape in ACTION_SCHEMAS.items():
    props={k:{} for k in _shape['allowed']};schema={'type':'object','properties':props,'required':_shape['required'],'additionalProperties':False}
    registry.register_action(_name,ACTION_LABELS[_name],schema,['write','external'] if _name in _EXTERNAL else ['write'],'external' if _name in _EXTERNAL else 'write')

def validate_action_payload(kind:str,payload:Any)->dict[str,Any]|None:
    shape=ACTION_SCHEMAS.get(kind)
    if not shape or not isinstance(payload,dict):return None
    if any(k not in shape['allowed'] for k in payload):return None
    if any(k not in payload or payload[k] in (None,'') for k in shape['required']):return None
    return payload
