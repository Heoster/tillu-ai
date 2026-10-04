"""Authenticated Brain↔Runtime RPC signing with bounded replay protection."""
import hashlib,hmac,json,time,uuid
import httpx
from .config import settings

_WINDOW=90
_seen:dict[str,float]={}
def _secret():
    if len(settings.tillu_internal_secret)<24:raise RuntimeError('TILLU_INTERNAL_SECRET is not configured')
    return settings.tillu_internal_secret.encode()
def _canonical(timestamp,request_id,source,target,body):
    digest=hashlib.sha256(body).hexdigest();return f'{timestamp}\n{request_id}\n{source}\n{target}\n{digest}'.encode()
def signed_headers(body:bytes,target='runtime'):
    ts=str(int(time.time()));rid=str(uuid.uuid4());source=settings.service_role;sig=hmac.new(_secret(),_canonical(ts,rid,source,target,body),hashlib.sha256).hexdigest()
    return {'X-Tillu-Timestamp':ts,'X-Tillu-Request-Id':rid,'X-Tillu-Source':source,'X-Tillu-Target':target,'X-Tillu-Signature':sig,'Content-Type':'application/json'}
def verify_headers(body:bytes,headers,target):
    headers={str(k).lower():v for k,v in headers.items()}
    try:ts=int(headers.get('x-tillu-timestamp',''));rid=headers.get('x-tillu-request-id','');source=headers.get('x-tillu-source','');claimed=headers.get('x-tillu-target','');sig=headers.get('x-tillu-signature','')
    except Exception:raise PermissionError('Invalid internal RPC headers')
    now=time.time()
    for key,expiry in list(_seen.items()):
        if expiry<now:_seen.pop(key,None)
    if abs(now-ts)>_WINDOW or not rid or rid in _seen or claimed!=target or source not in {'brain','runtime'}:raise PermissionError('Expired, replayed, or misrouted internal request')
    expected=hmac.new(_secret(),_canonical(str(ts),rid,source,target,body),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig,expected):raise PermissionError('Invalid internal RPC signature')
    _seen[rid]=now+_WINDOW;return {'request_id':rid,'source':source}
async def runtime_rpc(capability:str,payload:dict,user_id:str,idempotency_key:str|None=None):
    if settings.service_role!='brain':raise RuntimeError('Only Brain may initiate Runtime RPC')
    if not settings.runtime_internal_url:raise RuntimeError('RUNTIME_INTERNAL_URL is not configured')
    body=json.dumps({'capability':capability,'payload':payload,'user_id':user_id,'idempotency_key':idempotency_key},separators=(',',':')).encode();headers=signed_headers(body,'runtime')
    async with httpx.AsyncClient(timeout=60) as client:
        response=await client.post(settings.runtime_internal_url.rstrip('/')+'/api/internal/rpc',content=body,headers=headers);response.raise_for_status();return response.json()
