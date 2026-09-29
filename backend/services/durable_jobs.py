"""Private object storage and transactional job coordination; no inference here."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
import time
import httpx

from services.supabase_service import get_supabase_client

BUCKET = 'mediatruth-jobs'
logger = logging.getLogger(__name__)
_last_wake = 0.0


async def wake_worker():
    global _last_wake
    url = os.getenv('WORKER_URL', '')
    if not url or time.monotonic() - _last_wake < 30:
        return
    _last_wake = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(url.rstrip('/')+'/wake',
                              headers={'Authorization': 'Bearer '+os.environ['WORKER_SECRET']})
    except Exception:
        logger.info('worker_wake_pending')


class DurableJobs:
    def __init__(self):
        self.client = get_supabase_client()
        self.bucket = self.client.storage.from_(BUCKET)

    async def call(self, action, **args):
        return await asyncio.wait_for(asyncio.to_thread(
            lambda: self.client.rpc('media_job_action', {'p_action': action, 'p_args': args}).execute().data
        ), 15)

    async def checkin(self):
        await asyncio.to_thread(lambda: self.client.table('media_worker_health').upsert(
            {'id': 1, 'last_seen': datetime.now(timezone.utc).isoformat()}).execute())

    async def worker_online(self):
        rows = await asyncio.to_thread(lambda: self.client.table('media_worker_health')
                                      .select('last_seen').eq('id', 1).execute().data)
        return bool(rows and datetime.fromisoformat(rows[0]['last_seen'].replace('Z', '+00:00'))
                    > datetime.now(timezone.utc) - timedelta(seconds=150))

    @staticmethod
    def path(job, output=False):
        return f"{job['owner']}/{job['id']}/{'output.png' if output else 'input'}"

    async def upload_url(self, job, output=False):
        return await asyncio.to_thread(self.bucket.create_signed_upload_url, self.path(job, output))

    async def download_url(self, job, output=False):
        value = await asyncio.to_thread(self.bucket.create_signed_url, self.path(job, output), 120)
        return value['signedURL']

    async def check_object(self, job, output=False):
        info = await asyncio.to_thread(self.bucket.info, self.path(job, output))
        size = info.get('size', info.get('metadata', {}).get('size'))
        if size is None or not 0 < int(size) <= 50_000_000:
            raise ValueError('Stored file exceeds cloud limits')
        if not output and int(size) != job['byte_size']:
            raise ValueError('Stored file size differs from reservation')

    async def cleanup(self):
        """Retry deletions; do not release quota until storage confirms deletion.

        Signed upload URLs live for two hours. Sweep terminal inputs again after
        24 hours so a late upload cannot permanently escape cleanup.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        rows = await asyncio.to_thread(lambda: self.client.table('media_jobs').select('*')
            .in_('status', ['completed', 'failed', 'cancelled'])
            .or_(f'input_deleted.eq.false,and(output_deleted.eq.false,created_at.lt.{cutoff})')
            .order('created_at').limit(100).execute().data)
        for row in rows:
            try:
                expired = row['created_at'] < cutoff
                paths = [self.path(row)]
                if expired:
                    paths.append(self.path(row, True))
                await asyncio.to_thread(self.bucket.remove, paths)
                updates = {'input_deleted': True}
                if expired:
                    updates['output_deleted'] = True
                await asyncio.to_thread(lambda: self.client.table('media_jobs').update(updates)
                                        .eq('id', row['id']).execute())
            except Exception:
                logger.warning('job_cleanup_failed', extra={'job_id': row['id']})


def public_job(job):
    result = job.get('result') if job['status'] == 'completed' else None
    if result is not None and job['kind'] != 'clean':
        result = {'scan_id': job['id'], **result}
    return {key: job.get(key) for key in ('id', 'status', 'stage', 'error', 'cancel_requested')} | {
        'result': result, 'operation': job['kind']}
