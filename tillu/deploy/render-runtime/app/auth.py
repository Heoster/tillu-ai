import hmac, hashlib, time as _time
from dataclasses import dataclass
from fastapi import Header, Query, HTTPException
from .config import settings

@dataclass
class User:
    id:str
    email:str|None=None

_UI_TOKEN_TTL = 3600  # 1 hour

def _sign(payload: str) -> str:
    return hmac.new(settings.tillu_internal_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

def mint_ui_token() -> str:
    """Create a short-lived HMAC token for the runtime UI. Valid for 1 hour."""
    exp = int(_time.time()) + _UI_TOKEN_TTL
    payload = f"ui:{exp}:{settings.owner_user_id}"
    sig = _sign(payload)
    return f"{payload}.{sig}"

def verify_ui_token(token: str) -> User:
    """Verify a UI token minted by mint_ui_token(). Raises HTTPException on failure."""
    try:
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError("malformed")
        payload, sig = parts
        expected = _sign(payload)
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        prefix, exp_str, uid = payload.split(":", 2)
        if prefix != "ui":
            raise ValueError("wrong type")
        if int(exp_str) < int(_time.time()):
            raise HTTPException(401, "UI token expired — refresh the page")
        return User(uid)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid UI token")

def current_user(
    authorization: str | None = Header(default=None),
    ui_token: str | None = Query(default=None, alias="_t"),
) -> User:
    # UI self-auth token (HMAC, minted server-side, embedded in page)
    if ui_token:
        return verify_ui_token(ui_token)
    # Development fallback — only when Supabase is not configured
    if not settings.supabase_url:
        if settings.environment == "production":
            raise HTTPException(503, "Supabase authentication is not configured")
        return User("00000000-0000-0000-0000-000000000001", "heoster@local")
    # Normal Supabase JWT path
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    from supabase import create_client
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    try:
        response = client.auth.get_user(authorization[7:])
        u = response.user
        if not u:
            raise ValueError()
        user = User(str(u.id), u.email)
        id_match = bool(settings.owner_user_id and user.id == settings.owner_user_id)
        email_match = bool(settings.owner_email and (user.email or "").lower() == settings.owner_email.lower())
        if not (id_match or email_match):
            raise HTTPException(403, "TILLU is private and only Heoster's configured owner account may access it")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid or expired session")
