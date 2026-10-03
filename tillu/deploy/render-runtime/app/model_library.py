"""Provider model catalog and live discovery for TILLU.

Static entries are conservative free/free-tier defaults from official docs. Live
catalog calls add currently visible models when credentials permit; discovery never
claims that an unconfigured model is callable.
"""
from __future__ import annotations
import asyncio
from datetime import datetime,timezone
from typing import Any
import httpx
from .config import settings

SOURCES={
 'groq':'https://console.groq.com/docs/models',
 'cerebras':'https://inference-docs.cerebras.ai/support/pricing',
 'openrouter':'https://openrouter.ai/docs/guides/routing/routers/free-router',
 'cloudflare':'https://developers.cloudflare.com/workers-ai/platform/pricing/',
 'google':'https://ai.google.dev/gemini-api/docs/models'
}
CURATED=[
 # Groq active catalog: production, preview, audio, guard, and speech models.
 {'provider':'groq','id':'llama-3.1-8b-instant','name':'Llama 3.1 8B Instant','free_tier':True,'capabilities':['chat','fast'],'context':131072,'recommended_for':['intent'],'stage':'production'},
 {'provider':'groq','id':'llama-3.3-70b-versatile','name':'Llama 3.3 70B Versatile','free_tier':True,'capabilities':['chat','reasoning'],'context':131072,'recommended_for':['planning','execution'],'stage':'production'},
 {'provider':'groq','id':'openai/gpt-oss-20b','name':'GPT-OSS 20B','free_tier':True,'capabilities':['chat','reasoning','structured-output','tools'],'context':131072,'recommended_for':['intent','planning','execution'],'stage':'production'},
 {'provider':'groq','id':'openai/gpt-oss-120b','name':'GPT-OSS 120B','free_tier':True,'capabilities':['chat','reasoning','structured-output','tools'],'context':131072,'recommended_for':['planning','execution'],'stage':'production'},
 {'provider':'groq','id':'whisper-large-v3','name':'Whisper Large V3','free_tier':True,'capabilities':['speech-to-text'],'context':None,'recommended_for':['transcription'],'stage':'production'},
 {'provider':'groq','id':'whisper-large-v3-turbo','name':'Whisper Large V3 Turbo','free_tier':True,'capabilities':['speech-to-text','fast'],'context':None,'recommended_for':['transcription'],'stage':'production'},
 {'provider':'groq','id':'canopylabs/orpheus-arabic-saudi','name':'Orpheus Arabic Saudi','free_tier':True,'capabilities':['text-to-speech','arabic'],'context':4000,'recommended_for':['speech'],'stage':'preview'},
 {'provider':'groq','id':'canopylabs/orpheus-v1-english','name':'Orpheus V1 English','free_tier':True,'capabilities':['text-to-speech','english'],'context':4000,'recommended_for':['speech'],'stage':'preview'},
 {'provider':'groq','id':'meta-llama/llama-prompt-guard-2-22m','name':'Llama Prompt Guard 2 22M','free_tier':True,'capabilities':['safety','classification'],'context':512,'recommended_for':['guard'],'stage':'preview'},
 {'provider':'groq','id':'meta-llama/llama-prompt-guard-2-86m','name':'Llama Prompt Guard 2 86M','free_tier':True,'capabilities':['safety','classification'],'context':512,'recommended_for':['guard'],'stage':'preview'},
 {'provider':'groq','id':'minimaxai/minimax-m2.7','name':'MiniMax M2.7','free_tier':False,'capabilities':['chat','reasoning'],'context':196608,'recommended_for':['planning','execution'],'stage':'preview'},
 {'provider':'groq','id':'openai/gpt-oss-safeguard-20b','name':'Safety GPT-OSS 20B','free_tier':True,'capabilities':['safety','reasoning'],'context':131072,'recommended_for':['guard'],'stage':'preview'},
 {'provider':'groq','id':'qwen/qwen3.8-27b','name':'Qwen 3.8 27B','free_tier':True,'capabilities':['chat','reasoning','structured-output'],'context':131072,'recommended_for':['planning','execution'],'stage':'preview'},
 # Cerebras Shared Inference currently documents both models for Free Trial and PAYG.
 {'provider':'cerebras','id':'gpt-oss-120b','name':'GPT-OSS 120B','free_tier':True,'capabilities':['chat','reasoning'],'context':65536,'recommended_for':['planning','execution'],'stage':'production'},
 {'provider':'cerebras','id':'qwen-3.8-27b','name':'Qwen 3.8 27B','free_tier':True,'capabilities':['chat','reasoning'],'context':64000,'recommended_for':['planning','execution'],'stage':'production'},
 {'provider':'openrouter','id':'openrouter/free','name':'Free Models Router','free_tier':True,'capabilities':['chat','dynamic-routing'],'context':None,'recommended_for':['intent','planning','execution'],'stage':'production'},
 {'provider':'cloudflare','id':'@cf/qwen/qwen3-30b-a3b-fp8','name':'Qwen 3 30B A3B','free_tier':True,'capabilities':['chat','reasoning','edge'],'context':None,'recommended_for':['intent','execution'],'stage':'production'},
 {'provider':'cloudflare','id':'@cf/openai/gpt-oss-120b','name':'GPT-OSS 120B','free_tier':True,'capabilities':['chat','reasoning','edge'],'context':None,'recommended_for':['planning','execution'],'stage':'production'},
 {'provider':'google','id':'gemini-2.5-flash','name':'Gemini 2.5 Flash','free_tier':True,'capabilities':['chat','vision','long-context','tools','reasoning'],'context':1048576,'recommended_for':['planning','execution'],'stage':'production'},
 {'provider':'google','id':'gemini-3.1-flash-lite','name':'Gemini 3.1 Flash-Lite','free_tier':True,'capabilities':['chat','vision','long-context','tools','reasoning'],'context':1000000,'recommended_for':['planning','execution'],'stage':'production'},
 {'provider':'google','id':'gemini-3-flash-preview','name':'Gemini 3 Flash Preview','free_tier':True,'capabilities':['chat','vision','long-context','tools','reasoning'],'context':1000000,'recommended_for':['planning','execution'],'stage':'preview'},
]

def configured(provider:str)->bool:
 return {'groq':bool(settings.groq_api_key),'cerebras':bool(settings.cerebras_api_key),'openrouter':bool(settings.openrouter_api_key),'cloudflare':bool(settings.cloudflare_account_id and settings.cloudflare_api_token),'google':bool(settings.google_api_key)}[provider]

def _row(provider:str,raw:dict[str,Any]):
 mid=str(raw.get('id') or raw.get('name') or raw.get('model') or '')
 return {'provider':provider,'id':mid,'name':raw.get('displayName') or raw.get('name') or mid,'free_tier':None,'capabilities':['chat'],'context':raw.get('context_length') or raw.get('inputTokenLimit'),'recommended_for':[],'live_discovered':True}

async def discover_provider(provider:str):
 headers={};url=''
 if provider=='groq':url='https://api.groq.com/openai/v1/models';headers={'Authorization':f'Bearer {settings.groq_api_key}'}
 elif provider=='cerebras':url='https://api.cerebras.ai/v1/models';headers={'Authorization':f'Bearer {settings.cerebras_api_key}'}
 elif provider=='openrouter':
  url='https://openrouter.ai/api/v1/models'
  if settings.openrouter_api_key:headers={'Authorization':f'Bearer {settings.openrouter_api_key}'}
 elif provider=='google':url=f'https://generativelanguage.googleapis.com/v1beta/models?key={settings.google_api_key}'
 elif provider=='cloudflare':url=f'https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/models/search?per_page=100&task=Text%20Generation';headers={'Authorization':f'Bearer {settings.cloudflare_api_token}'}
 else:return []
 async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
  response=await client.get(url,headers=headers);response.raise_for_status();payload=response.json()
 rows=payload.get('data') or payload.get('models') or payload.get('result') or []
 out=[]
 for raw in rows:
  row=_row(provider,raw)
  if provider=='google':
   methods=raw.get('supportedGenerationMethods',[])
   if 'generateContent' not in methods:continue
   row['id']=row['id'].removeprefix('models/')
  if provider=='openrouter':
   pricing=raw.get('pricing') or {};free=row['id'].endswith(':free') or (str(pricing.get('prompt'))=='0' and str(pricing.get('completion'))=='0')
   row['free_tier']=free;row['capabilities']=['chat']+(['free'] if free else ['paid'])
  out.append(row)
 return out

async def build_library(refresh:bool=False):
 providers=['groq','cerebras','openrouter','cloudflare','google'];live=[];errors={}
 if refresh:
  async def one(p):
   if not configured(p) and p!='openrouter':return p,[],None
   try:return p,await discover_provider(p),None
   except Exception as exc:return p,[],type(exc).__name__
  for provider,rows,error in await asyncio.gather(*(one(p) for p in providers)):
   live.extend(rows)
   if error:errors[provider]=error
 merged={(x['provider'],x['id']):{**x,'configured':configured(x['provider']),'source':SOURCES[x['provider']],'live_discovered':False} for x in CURATED}
 for x in live:merged[(x['provider'],x['id'])]={**merged.get((x['provider'],x['id']),{}),**x,'configured':configured(x['provider']),'source':SOURCES[x['provider']]}
 return {'models':list(merged.values()),'providers':[{'id':p,'configured':configured(p),'source':SOURCES[p]} for p in providers],'refreshed_at':datetime.now(timezone.utc).isoformat(),'live_refresh':refresh,'errors':errors,'policy':'Curated free/free-tier defaults plus live provider discovery. Availability and quotas remain provider-controlled.'}
