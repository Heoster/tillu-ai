import ipaddress,socket
from urllib.parse import urlparse

BLOCKED_PORTS={0,22,25,53,110,135,137,138,139,143,445,465,587,993,995,1433,2375,2376,3306,5432,6379,8080,9200,11211,27017}

def validate_public_endpoint(url:str,https_only=False,allowed_domains:set[str]|None=None):
    p=urlparse(url)
    schemes={'https'} if https_only else {'http','https'}
    if p.scheme not in schemes or not p.hostname or p.username or p.password:raise ValueError('Invalid or unsupported URL')
    port=p.port or (443 if p.scheme=='https' else 80)
    if port in BLOCKED_PORTS or not 1<=port<=65535:raise ValueError('Destination port is blocked')
    host=p.hostname.rstrip('.').lower()
    if allowed_domains and host not in allowed_domains:raise ValueError('Domain is not in the trusted allowlist')
    addresses={item[4][0] for item in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)}
    if not addresses:raise ValueError('Host could not be resolved')
    for raw in addresses:
        ip=ipaddress.ip_address(raw)
        if not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:raise ValueError('Private or unsafe network target blocked')
    return {'scheme':p.scheme,'host':host,'port':port,'addresses':sorted(addresses)}

def reject_redirect(response):
    if 300<=response.status_code<400:raise ValueError('Redirects are not accepted; provide the final public URL')
