from dataclasses import dataclass,asdict,field
from collections import deque
from typing import Any
import time,json,re
import httpx
from .config import settings
from .model_adapters import build_model_adapters

@dataclass
class Provider:
    id:str;name:str;configured:bool;capabilities:list[str];priority:int;model:str
    phases:list[str];relative_cost:float;rpm:int;tpm:int
@dataclass
class Runtime:
    calls:deque=field(default_factory=deque);tokens:deque=field(default_factory=deque)
    cooldown_until:float=0;breaker_until:float=0;failures:int=0;latency_ewma:float=0;last_error:str|None=None

class ModelGateway:
    def __init__(self):self.runtime:dict[str,Runtime]={};self.last_route:dict[str,Any]={};self.adapters=build_model_adapters()
    def providers(self):
        """Free/free-tier model pool; each model is independently health-scored."""
        rows=[]
        def add(provider,name,configured,capabilities,priority,models,phases,cost,rpm,tpm):
            seen=set()
            for offset,model in enumerate(models):
                if not model or model in seen:continue
                seen.add(model);rows.append(Provider(provider,name,configured,capabilities,priority+offset,model,phases,cost+offset*.002,rpm,tpm))
        add('groq','Groq',bool(settings.groq_api_key),['chat','tools','fast','reasoning'],1,[settings.groq_model,'openai/gpt-oss-120b','llama-3.1-8b-instant','llama-3.3-70b-versatile','qwen/qwen3.8-27b'],['intent','planning','execution'],0.08,30,12000)
        add('cloudflare','Cloudflare Workers AI',bool(settings.cloudflare_api_token and settings.cloudflare_account_id),['chat','fast','edge'],3,[settings.cloudflare_model,'@cf/openai/gpt-oss-120b'],['intent','execution'],0.05,40,10000)
        add('google','Google Gemini',bool(settings.google_api_key),['chat','vision','long-context','tools','reasoning'],4,[settings.google_model,'gemini-2.5-flash','gemini-3-flash-preview'],['planning','execution'],0.18,15,250000)
        add('openrouter','OpenRouter',bool(settings.openrouter_api_key),['chat','fallback','model-variety','reasoning'],5,[settings.openrouter_model],['intent','planning','execution'],0.12,20,20000)
        return rows
    def _rt(self,p):return self.runtime.setdefault(f'{p.id}:{p.model}',Runtime())
    def _prune(self,r,now):
        while r.calls and r.calls[0]<now-60:r.calls.popleft()
        while r.tokens and r.tokens[0][0]<now-60:r.tokens.popleft()
    def _available(self,p,estimated_tokens):
        now=time.time();r=self._rt(p);self._prune(r,now)
        return p.configured and now>=max(r.cooldown_until,r.breaker_until) and len(r.calls)<max(1,p.rpm-2) and sum(x[1] for x in r.tokens)+estimated_tokens<max(100,p.tpm-int(p.tpm*.1))
    def candidates(self,required=None,phase='execution',estimated_tokens=1000):
        required=required or ['chat'];rows=[]
        for p in self.providers():
            if phase not in p.phases or not all(x in p.capabilities for x in required) or not self._available(p,estimated_tokens):continue
            r=self._rt(p);latency=r.latency_ewma or 900
            # Cost first, then health/latency. Planning rewards reasoning capability.
            score=p.relative_cost+(latency/1000)*.015+r.failures*.2-(.03 if phase=='planning' and 'reasoning' in p.capabilities else 0)
            rows.append((score,p))
        return [p for _,p in sorted(rows,key=lambda x:x[0])]
    def status(self):
        now=time.time();out=[]
        for p in self.providers():
            r=self._rt(p);self._prune(r,now);out.append({**asdict(p),'route_id':f'{p.id}:{p.model}','healthy':p.configured and now>=r.breaker_until,'available':self._available(p,1),'rpm_used':len(r.calls),'rpm_limit':p.rpm,'tokens_used_60s':sum(x[1] for x in r.tokens),'tpm_limit':p.tpm,'latency_ms':round(r.latency_ewma),'cooldown_seconds':max(0,round(max(r.cooldown_until,r.breaker_until)-now)),'last_error':r.last_error})
        return out
    async def chat(self,messages,required=None,phase='execution',max_tokens=1200):
        estimate=max_tokens+sum(len(m.get('content','')) for m in messages)//4;candidates=self.candidates(required,phase,estimate)
        if not candidates:return None
        errors=[]
        for p in candidates:
            r=self._rt(p);started=time.perf_counter();r.calls.append(time.time());r.tokens.append((time.time(),estimate))
            try:
                result=await self._call(p,messages,max_tokens);latency=(time.perf_counter()-started)*1000;r.latency_ewma=latency if not r.latency_ewma else .7*r.latency_ewma+.3*latency
                if latency>5000 and len(candidates)>1:raise TimeoutError('latency threshold exceeded')
                r.failures=max(0,r.failures-1);r.last_error=None
                result['route']={'phase':phase,'provider':p.id,'model':p.model,'latency_ms':round(latency),'estimated_tokens':estimate};self.last_route=result['route'];return result
            except httpx.HTTPStatusError as exc:
                code=exc.response.status_code;r.last_error=f'HTTP {code}';r.failures+=1
                if code==429:
                    retry=exc.response.headers.get('retry-after','60');r.cooldown_until=time.time()+(float(retry) if str(retry).replace('.','',1).isdigit() else 60)
                elif code>=500:r.breaker_until=time.time()+min(300,15*(2**min(r.failures,4)))
                errors.append(f'{p.id}:HTTP{code}')
            except Exception as exc:
                r.last_error=type(exc).__name__;r.failures+=1;r.breaker_until=time.time()+min(180,10*(2**min(r.failures,4)));errors.append(f'{p.id}:{type(exc).__name__}')
        raise RuntimeError('All available providers failed: '+', '.join(errors))
    async def json_chat(self,messages,phase,max_tokens=500):
        result=await self.chat(messages,phase=phase,max_tokens=max_tokens)
        if not result:return None
        raw=result['text'].strip();match=re.search(r'\{.*\}',raw,re.S)
        if not match:raise ValueError('Model did not return JSON')
        result['json']=json.loads(match.group(0));return result
    async def _call(self,p,messages,max_tokens):
        adapter=self.adapters.get(p.id)
        if not adapter:raise ValueError('Unknown provider')
        return await adapter.complete(p.model,messages,max_tokens)
    async def _openai(self,url,key,p,messages,max_tokens,extra=None):
        async with httpx.AsyncClient(timeout=45) as c:
            r=await c.post(url,headers={'Authorization':f'Bearer {key}',**(extra or {})},json={'model':p.model,'messages':messages,'temperature':0.15,'max_tokens':max_tokens});r.raise_for_status();d=r.json();u=d.get('usage') or {}
            return {'text':d['choices'][0]['message']['content'],'provider':p.id,'model':p.model,'usage':u}
    async def _gemini(self,messages,p,max_tokens):
        system='\n'.join(m['content'] for m in messages if m['role']=='system');contents=[{'role':'model' if m['role']=='assistant' else 'user','parts':[{'text':m['content']}]} for m in messages if m['role']!='system'];payload={'contents':contents,'generationConfig':{'temperature':.15,'maxOutputTokens':max_tokens}}
        if system:payload['systemInstruction']={'parts':[{'text':system}]}
        async with httpx.AsyncClient(timeout=60) as c:
            r=await c.post(f'https://generativelanguage.googleapis.com/v1beta/models/{p.model}:generateContent?key={settings.google_api_key}',json=payload);r.raise_for_status();d=r.json();text=''.join(x.get('text','') for x in d['candidates'][0]['content']['parts']);return {'text':text,'provider':p.id,'model':p.model,'usage':d.get('usageMetadata')}
    async def _cloudflare(self,messages,p,max_tokens):
        async with httpx.AsyncClient(timeout=45) as c:
            r=await c.post(f'https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/run/{p.model}',headers={'Authorization':f'Bearer {settings.cloudflare_api_token}'},json={'messages':messages,'max_tokens':max_tokens,'temperature':.15});r.raise_for_status();d=r.json();x=d.get('result',{});return {'text':x.get('response') or x.get('result') or '', 'provider':p.id,'model':p.model,'usage':x.get('usage')}
gateway=ModelGateway()
