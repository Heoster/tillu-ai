"""Required production Honcho memory and dialectic adapter."""
from __future__ import annotations
import asyncio
from .config import settings

class HonchoMemory:
    def __init__(self):self.client=None;self.user=None;self.assistant=None
    @property
    def configured(self):return bool(settings.honcho_api_key and settings.honcho_workspace_id and settings.honcho_base_url)
    def _init(self):
        if self.client:return
        if not self.configured:raise RuntimeError('Honcho is required but not configured')
        from honcho import Honcho
        kwargs={'workspace_id':settings.honcho_workspace_id,'api_key':settings.honcho_api_key,'environment':'production'}
        if settings.honcho_base_url:kwargs['base_url']=settings.honcho_base_url
        self.client=Honcho(**kwargs);self.user=self.client.peer(settings.honcho_user_peer);self.assistant=self.client.peer(settings.honcho_assistant_peer)
    async def health(self):
        self._init()
        try:
            await asyncio.wait_for(asyncio.to_thread(self.client.get_metadata),15);return {'configured':True,'reachable':True,'workspace':settings.honcho_workspace_id}
        except Exception as exc:return {'configured':True,'reachable':False,'workspace':settings.honcho_workspace_id,'error':type(exc).__name__}
    async def ingest_exchange(self,conversation_id,user_text,assistant_text):
        self._init()
        def work():
            session=self.client.session(conversation_id);session.add_peers([self.user,self.assistant]);session.add_messages([self.user.message(user_text[:25000]),self.assistant.message(assistant_text[:25000])])
        await asyncio.wait_for(asyncio.to_thread(work),30)
    async def recall(self,query,conversation_id=None):
        self._init()
        def work():
            kwargs={'reasoning_level':settings.honcho_reasoning_level}
            if conversation_id:kwargs['session']=conversation_id
            return self.user.chat(query[:10000],**kwargs)
        value=await asyncio.wait_for(asyncio.to_thread(work),45)
        return str(value)[:8000]
    async def session_context(self,conversation_id,tokens=3000):
        self._init()
        def work():
            context=self.client.session(conversation_id).context(summary=True,tokens=min(max(tokens,500),10000),peer_target=settings.honcho_user_peer,peer_perspective=settings.honcho_assistant_peer)
            return str(context)
        return (await asyncio.wait_for(asyncio.to_thread(work),30))[:20000]

honcho_memory=HonchoMemory()
