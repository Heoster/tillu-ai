import hashlib
from pathlib import Path
import httpx
from .netpolicy import validate_public_endpoint,reject_redirect

MAX_BYTES=25*1024*1024
TRUSTED_DOWNLOAD_DOMAINS={'cbse.gov.in','www.cbse.gov.in','cbseacademic.nic.in','www.cbseacademic.nic.in'}
LIBRARY=Path(__file__).resolve().parent.parent/'library';LIBRARY.mkdir(exist_ok=True)

async def download_trusted_pdf(url:str)->dict:
    validate_public_endpoint(url,https_only=True,allowed_domains=TRUSTED_DOWNLOAD_DOMAINS)
    async with httpx.AsyncClient(timeout=45,follow_redirects=False) as client:
        async with client.stream('GET',url,headers={'User-Agent':'TILLU-Study-Agent/0.6'}) as response:
            reject_redirect(response);response.raise_for_status();ctype=response.headers.get('content-type','').lower()
            if 'pdf' not in ctype:raise ValueError('Source did not return a PDF')
            digest=hashlib.sha256();data=bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk);digest.update(chunk)
                if len(data)>MAX_BYTES:raise ValueError('PDF exceeds 25 MB safety limit')
    if bytes(data[:5])!=b'%PDF-':raise ValueError('Invalid PDF signature')
    sha=digest.hexdigest();path=LIBRARY/f'{sha}.pdf';deduplicated=path.exists()
    if not deduplicated:path.write_bytes(data)
    return {'sha256':sha,'size':len(data),'internal_path':str(path),'source_url':url,'mime_type':'application/pdf','deduplicated':deduplicated}
