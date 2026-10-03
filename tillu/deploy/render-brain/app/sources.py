import asyncio
from datetime import datetime,timezone
from typing import Any
import httpx
from .config import settings
from .search_adapters import build_search_adapters

class PublicSources:
    def __init__(self): self.timeout=httpx.Timeout(20);self.search_adapters=build_search_adapters()
    async def weather(self,latitude=29.97,longitude=77.55):
        params={"latitude":latitude,"longitude":longitude,"current":"temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m","daily":"temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset","timezone":"Asia/Kolkata","forecast_days":7}
        async with httpx.AsyncClient(timeout=self.timeout) as c:r=await c.get("https://api.open-meteo.com/v1/forecast",params=params);r.raise_for_status();d=r.json()
        return {"provider":"Open-Meteo","attribution":"Weather data by Open-Meteo (CC BY 4.0)","location":{"latitude":latitude,"longitude":longitude},"current":d.get("current"),"daily":d.get("daily"),"fetched_at":datetime.now(timezone.utc).isoformat()}
    async def news(self,query="India technology education",limit=12):
        params={"query":query,"mode":"artlist","format":"json","maxrecords":min(limit,50),"sort":"datedesc","timespan":"2d"}
        try:
            async with httpx.AsyncClient(timeout=30) as c:r=await c.get("https://api.gdeltproject.org/api/v2/doc/doc",params=params);r.raise_for_status();d=r.json()
            return {"provider":"GDELT","items":[{"title":x.get("title"),"url":x.get("url"),"domain":x.get("domain"),"language":x.get("language"),"seen_at":x.get("seendate"),"image":x.get("socialimage")} for x in d.get("articles",[])[:limit]],"fetched_at":datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            fallback=await self.web_search(query,limit)
            return {"provider":fallback.get('provider','search fallback'),"items":[{'title':x.get('title'),'url':x.get('url'),'domain':x.get('source'),'summary':x.get('content')} for x in fallback.get('results',[])],"fallback_errors":[f'gdelt:{type(exc).__name__}',*fallback.get('fallback_errors',[])],"fetched_at":datetime.now(timezone.utc).isoformat()}
    async def hacker_news(self,limit=12):
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            ids=(await c.get("https://hacker-news.firebaseio.com/v0/topstories.json")).json()[:limit]
            rows=await asyncio.gather(*[c.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json") for i in ids])
        return {"provider":"Hacker News","items":[{"title":r.json().get("title"),"url":r.json().get("url") or f"https://news.ycombinator.com/item?id={r.json().get('id')}","score":r.json().get("score"),"comments":r.json().get("descendants",0)} for r in rows],"fetched_at":datetime.now(timezone.utc).isoformat()}
    async def wikipedia(self,query,limit=5):
        params={"action":"query","generator":"search","gsrsearch":query,"gsrlimit":limit,"prop":"extracts|info","exintro":1,"explaintext":1,"inprop":"url","format":"json","origin":"*"}
        async with httpx.AsyncClient(timeout=self.timeout,headers={"User-Agent":"TILLU/0.5 (educational personal assistant; contact codeex@email.com)"}) as c:r=await c.get("https://en.wikipedia.org/w/api.php",params=params);r.raise_for_status();d=r.json()
        pages=list(d.get("query",{}).get("pages",{}).values())
        return [{"title":x.get("title"),"url":x.get("fullurl"),"content":x.get("extract","")[:1200],"source":"Wikipedia"} for x in pages]
    async def web_search(self,query,limit=6):
        errors=[]
        for provider in [x.strip().lower() for x in settings.search_provider_order.split(',')]:
            try:
                if provider=='wikipedia':return {'provider':'Wikipedia','results':await self.wikipedia(query,limit),'fallback_errors':errors}
                adapter=self.search_adapters.get(provider)
                if adapter and adapter.configured:return await adapter.search(query,limit)
            except Exception as exc:errors.append(f'{provider}:{type(exc).__name__}')
        return {'provider':'Wikipedia','results':await self.wikipedia(query,limit),'fallback_errors':errors}

sources=PublicSources()
