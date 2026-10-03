"""Optional Supabase cloud adapter. Local mode remains fully usable without credentials."""
from pathlib import Path
from typing import Any
from .config import settings

class CloudStore:
    def __init__(self):
        self.client=None
        if settings.supabase_url and settings.supabase_service_role_key:
            from supabase import create_client
            self.client=create_client(settings.supabase_url,settings.supabase_service_role_key)
    @property
    def enabled(self): return self.client is not None
    def upsert_job(self,job:dict[str,Any]):
        if not self.client:return
        self.client.table("jobs").upsert(job).execute()
    def upsert_progress(self,row:dict[str,Any]):
        if not self.client:return
        self.client.table("topic_progress").upsert(row).execute()
    def audit(self,row:dict[str,Any]):
        if not self.client:return
        self.client.table("audit_events").insert(row).execute()
    def enqueue_job(self,user_id:str,kind:str,payload:dict,idempotency_key:str):
        if not self.client:return None
        row={"user_id":user_id,"kind":kind,"payload":payload,"idempotency_key":idempotency_key,"status":"queued"}
        result=self.client.table("jobs").upsert(row,on_conflict="user_id,idempotency_key").execute()
        return result.data[0] if result.data else None
    def claim_jobs(self,worker:str,batch_size:int=5,lease_seconds:int=120):
        if not self.client:return []
        return self.client.rpc("claim_jobs",{"worker":worker,"batch_size":batch_size,"lease_seconds":lease_seconds}).execute().data or []
    def enqueue_due_automations(self,batch_size:int=50):
        if not self.client:return 0
        return int(self.client.rpc("enqueue_due_automations",{"batch_size":batch_size}).execute().data or 0)
    def complete_job(self,job_id:str,worker:str,status:str,result:dict|None=None,error:str|None=None):
        if not self.client:return
        patch={"status":status,"result":result,"last_error":error,"lease_until":None,"leased_by":None}
        self.client.table("jobs").update(patch).eq("id",job_id).eq("leased_by",worker).execute()
    def consume_quota(self,user_id:str,provider:str,operation:str,units:int,request_id:str|None=None):
        if not self.client:return True
        return bool(self.client.rpc("consume_quota",{"uid":user_id,"provider_name":provider,"operation_name":operation,"unit_count":units,"req_id":request_id}).execute().data)
    def upload_pdf(self,user_id:str,sha256:str,path:str)->dict:
        if not self.client:return {"cloud":False,"path":path}
        key=f"{user_id}/{sha256}.pdf"
        with open(path,"rb") as f:
            try:self.client.storage.from_("documents").upload(key,f,{"content-type":"application/pdf","upsert":"false"})
            except Exception as exc:
                # A content-addressed object may already exist; only suppress that case.
                if "already exists" not in str(exc).lower() and "duplicate" not in str(exc).lower():raise
        return {"cloud":True,"bucket":"documents","path":key}
    def upload_backup(self,user_id:str,name:str,data:bytes):
        if not self.client:raise RuntimeError('Cloud storage unavailable')
        key=f'{user_id}/{name}'
        self.client.storage.from_('backups').upload(key,data,{'content-type':'application/octet-stream','upsert':'false'})
        return {'bucket':'backups','path':key}
    def download_pdf(self,key:str)->bytes:
        if not self.client:raise RuntimeError("Cloud storage unavailable")
        return self.client.storage.from_("documents").download(key)
    def delete_pdf(self,key:str):
        if not self.client:raise RuntimeError("Cloud storage unavailable")
        return self.client.storage.from_("documents").remove([key])
cloud=CloudStore()
