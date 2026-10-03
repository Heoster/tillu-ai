from __future__ import annotations
import base64,httpx
from email.message import EmailMessage
from .config import settings

class Gmail:
    async def access_token(self):
        if not (settings.google_client_id and settings.google_client_secret and settings.gmail_refresh_token):raise RuntimeError('Gmail OAuth is not configured')
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.post('https://oauth2.googleapis.com/token',data={'client_id':settings.google_client_id,'client_secret':settings.google_client_secret,'refresh_token':settings.gmail_refresh_token,'grant_type':'refresh_token'});r.raise_for_status();return r.json()['access_token']
    async def request(self,method,path,**kwargs):
        token=await self.access_token()
        async with httpx.AsyncClient(timeout=25,headers={'Authorization':f'Bearer {token}'}) as c:
            r=await c.request(method,'https://gmail.googleapis.com/gmail/v1/users/me'+path,**kwargs);r.raise_for_status();return r.json() if r.content else {}
    async def list(self,query='',limit=20):
        data=await self.request('GET','/messages',params={'q':query,'maxResults':min(limit,50)})
        rows=[]
        for ref in data.get('messages',[])[:min(limit,20)]:
            m=await self.request('GET',f"/messages/{ref['id']}",params={'format':'metadata','metadataHeaders':['From','To','Subject','Date']});h={x['name'].lower():x['value'] for x in m.get('payload',{}).get('headers',[])};rows.append({'id':m['id'],'thread_id':m.get('threadId'),'from':h.get('from'),'subject':h.get('subject','(no subject)'),'date':h.get('date'),'snippet':m.get('snippet'),'labels':m.get('labelIds',[])})
        return rows
    async def read(self,message_id):return await self.request('GET',f'/messages/{message_id}',params={'format':'full'})
    async def draft(self,to,subject,body,thread_id=None):
        msg=EmailMessage();msg['To']=to;msg['Subject']=subject;msg.set_content(body);raw=base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip('=')
        data={'message':{'raw':raw}};
        if thread_id:data['message']['threadId']=thread_id
        return await self.request('POST','/drafts',json=data)
    async def send_draft(self,draft_id):return await self.request('POST','/drafts/send',json={'id':draft_id})

class WhatsApp:
    @property
    def configured(self):return bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)
    async def send_text(self,to,body):
        if not self.configured:raise RuntimeError('WhatsApp Cloud API is not configured')
        url=f'https://graph.facebook.com/v22.0/{settings.whatsapp_phone_number_id}/messages'
        payload={'messaging_product':'whatsapp','recipient_type':'individual','to':to,'type':'text','text':{'preview_url':False,'body':body}}
        async with httpx.AsyncClient(timeout=25,headers={'Authorization':f'Bearer {settings.whatsapp_access_token}'}) as c:r=await c.post(url,json=payload);r.raise_for_status();return r.json()

gmail=Gmail();whatsapp=WhatsApp()
