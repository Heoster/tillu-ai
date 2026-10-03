import re
import httpx
from bs4 import BeautifulSoup
from .netpolicy import validate_public_endpoint,reject_redirect
MAX_PAGE=2*1024*1024

async def read_page(url:str):
    validate_public_endpoint(url)
    async with httpx.AsyncClient(timeout=25,follow_redirects=False,headers={'User-Agent':'TILLU-Research/0.6'}) as c:
        async with c.stream('GET',url) as r:
            reject_redirect(r);r.raise_for_status();ctype=r.headers.get('content-type','')
            if 'text/html' not in ctype:raise ValueError('Only HTML research pages are supported')
            data=bytearray()
            async for chunk in r.aiter_bytes():
                data.extend(chunk)
                if len(data)>MAX_PAGE:raise ValueError('Page exceeds the 2 MB research limit')
    soup=BeautifulSoup(bytes(data),'html.parser')
    for tag in soup(['script','style','noscript','svg','nav','footer','iframe','object','embed']):tag.decompose()
    title=(soup.title.string.strip() if soup.title and soup.title.string else url)[:300]
    text=re.sub(r'\s+',' ',soup.get_text(' ',strip=True)).strip()[:120000]
    if len(text)<80:raise ValueError('Page did not contain enough readable text')
    return {'url':url,'final_url':url,'title':title,'content':text}
