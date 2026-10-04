"""Explicit adapters for every hosted model API used by TILLU."""
from __future__ import annotations
from typing import Protocol
import httpx
from .config import settings

class ModelAdapter(Protocol):
    id:str
    async def complete(self,model:str,messages:list[dict],max_tokens:int)->dict:...

class OpenAICompatibleAdapter:
    id='openai-compatible'
    def __init__(self,id,url,key,extra_headers=None):self.id=id;self.url=url;self.key=key;self.extra_headers=extra_headers or {}
    async def complete(self,model,messages,max_tokens):
        async with httpx.AsyncClient(timeout=45) as client:
            response=await client.post(self.url,headers={'Authorization':f'Bearer {self.key}',**self.extra_headers},json={'model':model,'messages':messages,'temperature':.15,'max_tokens':max_tokens});response.raise_for_status();data=response.json();usage=data.get('usage') or {}
        return {'text':data['choices'][0]['message']['content'],'provider':self.id,'model':model,'usage':usage}

class GeminiAdapter:
    id='google'
    async def complete(self,model,messages,max_tokens):
        system='\n'.join(x['content'] for x in messages if x['role']=='system');contents=[{'role':'model' if x['role']=='assistant' else 'user','parts':[{'text':x['content']}]} for x in messages if x['role']!='system'];payload={'contents':contents,'generationConfig':{'temperature':.15,'maxOutputTokens':max_tokens}}
        if system:payload['systemInstruction']={'parts':[{'text':system}]}
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.google_api_key}',json=payload);response.raise_for_status();data=response.json()
        text=''.join(x.get('text','') for x in data['candidates'][0]['content']['parts']);return {'text':text,'provider':self.id,'model':model,'usage':data.get('usageMetadata')}

class CloudflareAdapter:
    id='cloudflare'
    async def complete(self,model,messages,max_tokens):
        async with httpx.AsyncClient(timeout=45) as client:
            response=await client.post(f'https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/run/{model}',headers={'Authorization':f'Bearer {settings.cloudflare_api_token}'},json={'messages':messages,'max_tokens':max_tokens,'temperature':.15});response.raise_for_status();data=response.json();result=data.get('result',{})
        return {'text':result.get('response') or result.get('result') or '','provider':self.id,'model':model,'usage':result.get('usage')}

def build_model_adapters():
    return {
      'groq':OpenAICompatibleAdapter('groq','https://api.groq.com/openai/v1/chat/completions',settings.groq_api_key),
      'openrouter':OpenAICompatibleAdapter('openrouter','https://openrouter.ai/api/v1/chat/completions',settings.openrouter_api_key,{'HTTP-Referer':settings.public_app_url,'X-Title':'TILLU'}),
      'google':GeminiAdapter(),
      'cloudflare':CloudflareAdapter(),
    }
