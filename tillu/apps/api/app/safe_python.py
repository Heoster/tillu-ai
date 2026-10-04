"""A non-Turing-complete Python-syntax RPC runner.

It parses a strict AST subset; it never calls exec/eval or starts a shell/process.
"""
from __future__ import annotations
import ast,base64,hashlib,hmac,json,time
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from .config import settings
from .capabilities import registry,validate_action_payload
from .repository import create_action_proposal

MAX_SOURCE=12000;MAX_AST_NODES=500;MAX_STATEMENTS=40;MAX_CALLS=12;MAX_OUTPUT=30000

def _secret():
    if not settings.rpc_capability_secret:raise RuntimeError('RPC_CAPABILITY_SECRET is not configured')
    return settings.rpc_capability_secret.encode()
def issue_token(user_id:str,capabilities:list[str],ttl=300)->str:
    allowed=sorted(set(capabilities));unknown=set(allowed)-set(registry.tools)
    if unknown:raise ValueError('Unknown capabilities: '+', '.join(sorted(unknown)))
    payload={'sub':user_id,'cap':allowed,'exp':int(time.time())+min(max(ttl,30),900),'jti':str(uuid4())};raw=json.dumps(payload,separators=(',',':')).encode();sig=hmac.new(_secret(),raw,hashlib.sha256).digest();return base64.urlsafe_b64encode(raw).decode().rstrip('=')+'.'+base64.urlsafe_b64encode(sig).decode().rstrip('=')
def verify_token(token,user_id):
    try:
        a,b=token.split('.',1);raw=base64.urlsafe_b64decode(a+'='*(-len(a)%4));sig=base64.urlsafe_b64decode(b+'='*(-len(b)%4));payload=json.loads(raw)
    except Exception:raise ValueError('Invalid capability token')
    if not hmac.compare_digest(sig,hmac.new(_secret(),raw,hashlib.sha256).digest()):raise ValueError('Invalid capability token')
    if payload.get('sub')!=user_id or int(payload.get('exp',0))<int(time.time()):raise ValueError('Expired or owner-mismatched capability token')
    return payload

class Runner:
    def __init__(self,user_id,scopes):self.user_id=user_id;self.scopes=set(scopes);self.env={};self.calls=0;self.outputs=[]
    def value(self,node):
        if isinstance(node,ast.Constant):return node.value
        if isinstance(node,ast.Name):
            if node.id not in self.env:raise ValueError('Unknown variable: '+node.id)
            return self.env[node.id]
        if isinstance(node,ast.List):return [self.value(x) for x in node.elts]
        if isinstance(node,ast.Tuple):return [self.value(x) for x in node.elts]
        if isinstance(node,ast.Dict):return {self.value(k):self.value(v) for k,v in zip(node.keys,node.values)}
        if isinstance(node,ast.Subscript):return self.value(node.value)[self.value(node.slice)]
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):return self.value(node.left)+self.value(node.right)
        raise ValueError('Unsupported expression: '+type(node).__name__)
    async def call(self,node):
        if not isinstance(node.func,ast.Name) or node.func.id!='tool':raise ValueError('Only tool(name, args) calls are allowed')
        if len(node.args)!=2 or node.keywords:raise ValueError('tool requires exactly name and args')
        name=self.value(node.args[0]);args=self.value(node.args[1]);self.calls+=1
        if self.calls>MAX_CALLS:raise ValueError('RPC call limit exceeded')
        if name not in self.scopes:raise PermissionError('Capability is outside token scope')
        spec=registry.tools.get(name)
        if not spec:raise ValueError('Unknown capability')
        if spec.kind=='read':result=await registry.execute(name,args,self.user_id);self.outputs.append({'capability':name,'status':'completed','result':result});return result
        payload=validate_action_payload(name,args)
        if payload is None:raise ValueError('Invalid action payload')
        pid=str(uuid4());create_action_proposal({'id':pid,'user_id':self.user_id,'kind':name,'payload':payload,'status':'pending','created_at':datetime.now(timezone.utc).isoformat(),'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()});result={'status':'waiting_approval','proposal_id':pid};self.outputs.append({'capability':name,**result});return result
    async def run(self,source):
        if len(source)>MAX_SOURCE:raise ValueError('Source limit exceeded')
        tree=ast.parse(source,mode='exec');nodes=list(ast.walk(tree))
        if len(nodes)>MAX_AST_NODES or len(tree.body)>MAX_STATEMENTS:raise ValueError('Program complexity limit exceeded')
        forbidden=(ast.Import,ast.ImportFrom,ast.Attribute,ast.Lambda,ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.While,ast.For,ast.With,ast.Try,ast.Raise,ast.Delete,ast.Global,ast.Nonlocal,ast.Await,ast.Yield,ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)
        if any(isinstance(x,forbidden) for x in nodes):raise ValueError('Program contains a prohibited Python construct')
        for statement in tree.body:
            if isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name):
                value=await self.call(statement.value) if isinstance(statement.value,ast.Call) else self.value(statement.value);self.env[statement.targets[0].id]=value
            elif isinstance(statement,ast.Expr) and isinstance(statement.value,ast.Call):await self.call(statement.value)
            else:raise ValueError('Only assignments, literals, and tool calls are allowed')
            if len(json.dumps(self.outputs,default=str))>MAX_OUTPUT:raise ValueError('Output limit exceeded')
        return {'outputs':self.outputs,'variables':{k:v for k,v in self.env.items() if len(json.dumps(v,default=str))<4000}}

async def run_safe_python(source,token,user_id):
    payload=verify_token(token,user_id);return await Runner(user_id,payload['cap']).run(source)
