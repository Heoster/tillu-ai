import { authHeaders } from './cloud';

const KEY='tillu-sync-outbox';
const DEVICE_KEY='tillu-device-id';
export const deviceId=localStorage.getItem(DEVICE_KEY)||crypto.randomUUID();
localStorage.setItem(DEVICE_KEY,deviceId);

function read(){try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch{return[]}}
function write(items){localStorage.setItem(KEY,JSON.stringify(items))}
export function queueProgress(topicId,status,confidence){
  const items=read();items.push({id:crypto.randomUUID(),entity:'topic_progress',operation:'upsert',payload:{topic_id:topicId,status,confidence},client_time:new Date().toISOString()});write(items);return flush();
}
export async function flush(){
  if(!navigator.onLine)return {offline:true,pending:read().length};
  const mutations=read();if(!mutations.length)return {pending:0};
  try{const headers=await authHeaders();const r=await fetch('/api/sync/push',{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify({device_id:deviceId,mutations})});if(!r.ok)throw new Error('sync rejected');const d=await r.json();const accepted=new Set(d.accepted);write(mutations.filter(x=>!accepted.has(x.id)));return {pending:read().length}}
  catch{return {pending:mutations.length}}
}
window.addEventListener('online',()=>flush());
