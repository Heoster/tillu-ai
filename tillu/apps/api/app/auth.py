from dataclasses import dataclass
from fastapi import Header,HTTPException
from .config import settings

@dataclass
class User:
    id:str
    email:str|None=None

def current_user(authorization:str|None=Header(default=None))->User:
    # Development fallback is explicit and must never be enabled in production.
    if not settings.supabase_url:
        if settings.environment=="production":raise HTTPException(503,"Supabase authentication is not configured")
        return User("00000000-0000-0000-0000-000000000001","heoster@local")
    if not authorization or not authorization.startswith("Bearer "):raise HTTPException(401,"Missing bearer token")
    from supabase import create_client
    client=create_client(settings.supabase_url,settings.supabase_anon_key)
    try:
        response=client.auth.get_user(authorization[7:]);u=response.user
        if not u:raise ValueError()
        user=User(str(u.id),u.email)
        id_match=bool(settings.owner_user_id and user.id==settings.owner_user_id)
        email_match=bool(settings.owner_email and (user.email or '').lower()==settings.owner_email.lower())
        if not (id_match or email_match):raise HTTPException(403,"TILLU is private and only Heoster's configured owner account may access it")
        return user
    except HTTPException:raise
    except Exception:raise HTTPException(401,"Invalid or expired session")
