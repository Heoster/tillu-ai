import asyncio,sys,types
from app.config import settings
from app.honcho_adapter import HonchoMemory

def test_honcho_ingest_recall_and_context(monkeypatch):
    events=[]
    class Peer:
        def __init__(self,id):self.id=id
        def message(self,text):return (self.id,text)
        def chat(self,query,**kwargs):events.append(('chat',query,kwargs));return 'dialectic answer'
    class Session:
        def add_peers(self,peers):events.append(('peers',[x.id for x in peers]))
        def add_messages(self,messages):events.append(('messages',messages))
        def context(self,**kwargs):events.append(('context',kwargs));return 'session context'
    class Honcho:
        def __init__(self,**kwargs):events.append(('init',kwargs))
        def peer(self,id):return Peer(id)
        def session(self,id):events.append(('session',id));return Session()
        def get_metadata(self):return {}
    monkeypatch.setitem(sys.modules,'honcho',types.SimpleNamespace(Honcho=Honcho));monkeypatch.setattr(settings,'honcho_api_key','key');monkeypatch.setattr(settings,'honcho_workspace_id','tillu-test');monkeypatch.setattr(settings,'honcho_base_url','https://honcho.test')
    memory=HonchoMemory();assert asyncio.run(memory.health())['reachable']
    asyncio.run(memory.ingest_exchange('c1','hello','hi'))
    assert asyncio.run(memory.recall('preferences','c1'))=='dialectic answer'
    assert asyncio.run(memory.session_context('c1'))=='session context'
    assert any(x[0]=='messages' for x in events)
