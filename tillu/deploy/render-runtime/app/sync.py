from datetime import datetime,timezone
from pydantic import BaseModel,Field
from typing import Any,Literal
class Mutation(BaseModel):
    id:str
    entity:Literal["topic_progress","task"]
    operation:Literal["upsert","delete"]
    payload:dict[str,Any]
    client_time:str
class SyncPush(BaseModel):
    device_id:str
    mutations:list[Mutation]=Field(max_length=100)
class SyncCursor(BaseModel):
    since:str|None=None

def timestamp():return datetime.now(timezone.utc).isoformat()
