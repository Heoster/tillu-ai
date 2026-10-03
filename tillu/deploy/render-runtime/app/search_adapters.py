"""Adapters for TILLU's configured AI-oriented search APIs."""
import httpx
from .config import settings

class ParallelSearchAdapter:
 id='parallel'
 @property
 def configured(self):return bool(settings.parallel_api_key)
 async def search(self,query,limit):
  async with httpx.AsyncClient(timeout=40) as c:r=await c.post('https://api.parallel.ai/v1/search',headers={'x-api-key':settings.parallel_api_key,'Content-Type':'application/json'},json={'objective':query,'search_queries':[query],'mode':'basic','advanced_settings':{'max_results':limit,'excerpt_settings':{'max_chars_per_result':1600}}});r.raise_for_status();d=r.json()
  return {'provider':'Parallel','results':[{'title':x.get('title'),'url':x.get('url'),'content':'\n'.join(x.get('excerpts') or [])[:2400]} for x in d.get('results',[])]}
class YouSearchAdapter:
 id='you'
 @property
 def configured(self):return bool(settings.you_api_key)
 async def search(self,query,limit):
  async with httpx.AsyncClient(timeout=40) as c:r=await c.post('https://ydc-index.io/v1/search',headers={'X-API-Key':settings.you_api_key,'Content-Type':'application/json'},json={'query':query,'count':limit,'extraction':{'extraction_mode':'highlights'}});r.raise_for_status();d=r.json()
  rows=d.get('results',{}).get('web',d.get('hits',[]));return {'provider':'You.com','results':[{'title':x.get('title'),'url':x.get('url'),'content':x.get('description') or ' '.join(x.get('snippets') or x.get('highlights') or [])} for x in rows[:limit]]}
class TavilySearchAdapter:
 id='tavily'
 @property
 def configured(self):return bool(settings.tavily_api_key)
 async def search(self,query,limit):
  async with httpx.AsyncClient(timeout=30) as c:r=await c.post('https://api.tavily.com/search',json={'api_key':settings.tavily_api_key,'query':query,'max_results':limit,'search_depth':'basic','include_answer':False});r.raise_for_status();d=r.json()
  return {'provider':'Tavily','results':[{'title':x.get('title'),'url':x.get('url'),'content':x.get('content'),'score':x.get('score')} for x in d.get('results',[])]}
class FirecrawlSearchAdapter:
 id='firecrawl'
 @property
 def configured(self):return bool(settings.firecrawl_api_key)
 async def search(self,query,limit):
  async with httpx.AsyncClient(timeout=30) as c:r=await c.post('https://api.firecrawl.dev/v1/search',headers={'Authorization':f'Bearer {settings.firecrawl_api_key}'},json={'query':query,'limit':limit});r.raise_for_status();d=r.json()
  return {'provider':'Firecrawl','results':[{'title':x.get('title'),'url':x.get('url'),'content':x.get('description') or x.get('markdown','')[:900]} for x in d.get('data',[])]}
def build_search_adapters():return {x.id:x for x in (ParallelSearchAdapter(),YouSearchAdapter(),TavilySearchAdapter(),FirecrawlSearchAdapter())}
