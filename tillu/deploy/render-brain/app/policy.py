from dataclasses import dataclass
from urllib.parse import urlparse
import ipaddress, socket

TRUSTED_DOWNLOAD_DOMAINS={"cbse.gov.in","www.cbse.gov.in","cbseacademic.nic.in","www.cbseacademic.nic.in"}

@dataclass
class Decision:
    allowed: bool
    reason: str
    needs_approval: bool=True

def validate_download_url(url:str)->Decision:
    try:
        p=urlparse(url)
        if p.scheme!="https":return Decision(False,"Only HTTPS downloads are allowed")
        if not p.hostname:return Decision(False,"Missing hostname")
        if p.hostname not in TRUSTED_DOWNLOAD_DOMAINS:return Decision(False,"Domain is not in the trusted CBSE allowlist")
        for addr in socket.getaddrinfo(p.hostname,443):
            ip=ipaddress.ip_address(addr[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local:return Decision(False,"Private network targets are blocked")
        return Decision(True,"Trusted education source")
    except Exception:return Decision(False,"URL validation failed")
