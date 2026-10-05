import time, uuid
from collections import defaultdict, deque
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request:Request,call_next):
        request_id=request.headers.get('x-request-id') or str(uuid.uuid4())
        response=await call_next(request)
        response.headers['x-request-id']=request_id
        response.headers['x-content-type-options']='nosniff'
        response.headers['referrer-policy']='strict-origin-when-cross-origin'
        response.headers['cache-control']='no-store' if request.url.path.startswith('/api/') else 'public, max-age=300'
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Process-local guardrail. Use a shared Redis limiter when running multiple replicas."""
    def __init__(self,app,requests_per_minute:int=120):
        super().__init__(app);self.limit=requests_per_minute;self.hits=defaultdict(deque)
    async def dispatch(self,request:Request,call_next):
        # Health checks and browser-control (high-frequency mouse/stream) are exempt
        p=request.url.path
        if p in {'/api/health','/api/ready'} or p.startswith('/api/browser-control/'):return await call_next(request)
        now=time.monotonic();client=request.client.host if request.client else 'unknown';bucket=self.hits[client]
        while bucket and bucket[0]<now-60:bucket.popleft()
        if len(bucket)>=self.limit:return JSONResponse(status_code=429,content={'detail':'Too many requests. Try again shortly.'},headers={'retry-after':'60'})
        bucket.append(now);return await call_next(request)

class ServiceRoleBoundaryMiddleware(BaseHTTPMiddleware):
    """Runtime is internal-only except for health, browser UI, and browser-control routes."""
    def __init__(self,app,role='brain'):super().__init__(app);self.role=role
    async def dispatch(self,request:Request,call_next):
        path=request.url.path
        if self.role=='runtime':
            allowed=(
                path.startswith('/api/health') or
                path.startswith('/api/internal/') or
                path.startswith('/api/browser-control/') or
                path.startswith('/api/browser-ui') or
                path == '/browser-ui'
            )
            if not allowed:
                return JSONResponse(status_code=404,content={'detail':'Not found'})
        return await call_next(request)

class MaximumBodyMiddleware(BaseHTTPMiddleware):
    def __init__(self,app,max_bytes:int=27*1024*1024):super().__init__(app);self.max=max_bytes
    async def dispatch(self,request:Request,call_next):
        length=request.headers.get('content-length')
        if length and int(length)>self.max:return JSONResponse(status_code=413,content={'detail':'Request body too large'})
        return await call_next(request)
