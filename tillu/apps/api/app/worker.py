import asyncio,os,socket
from .cloud import cloud
from .sources import sources

WORKER_ID=os.getenv('WORKER_ID') or f'{socket.gethostname()}:{os.getpid()}'

async def process(job):
    kind=job['kind'];payload=job.get('payload') or {}
    if kind=='pyq_download':
        # Discovery is intentionally bounded; real file ingestion still applies trusted-domain policy.
        found=await sources.web_search('site:cbseacademic.nic.in class 12 sample paper PDF',6)
        return {'sources':found.get('results',[]),'plan_id':payload.get('plan_id')}
    if kind=='automation_run':return {'queued_automation':payload.get('automation_id')}
    raise ValueError(f'Unsupported job kind: {kind}')

async def main():
    if not cloud.enabled:raise RuntimeError('Worker requires Supabase production configuration')
    while True:
        jobs=await asyncio.to_thread(cloud.claim_jobs,WORKER_ID,5,180)
        if not jobs:await asyncio.sleep(5);continue
        for job in jobs:
            try:
                result=await asyncio.wait_for(process(job),timeout=150)
                await asyncio.to_thread(cloud.complete_job,job['id'],WORKER_ID,'completed',result,None)
            except Exception as exc:
                await asyncio.to_thread(cloud.complete_job,job['id'],WORKER_ID,'failed',None,f'{type(exc).__name__}: {str(exc)[:500]}')

if __name__=='__main__':asyncio.run(main())
