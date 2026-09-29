"""Hugging Face CPU worker. Triggered by real work; never sends keep-alive traffic."""
import asyncio
import hashlib
import hmac
import os
from pathlib import Path
import tempfile
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
from fastapi import FastAPI, HTTPException, Request
from services.jobs import run_isolated
from utils.file_utils import _check_image_magic, _check_video_magic

task = None


async def process(client, claim):
    job = claim['job']
    base = f"/worker/{job['id']}/"
    update = {'lease': job['lease']}
    with tempfile.TemporaryDirectory(prefix='mediatruth_remote_') as folder:
        path = Path(folder) / 'input'
        digest = hashlib.sha256()
        total = 0
        # The signed URL must never receive the backend worker credential.
        async with httpx.AsyncClient(timeout=60) as storage:
            async with storage.stream('GET', claim['download_url']) as response:
                response.raise_for_status()
                with path.open('wb') as stream:
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > min(job['byte_size'], 50_000_000):
                            raise ValueError('Upload exceeds reservation')
                        digest.update(chunk)
                        stream.write(chunk)
        if total != job['byte_size'] or digest.hexdigest() != job['input_sha256']:
            raise ValueError('Upload digest mismatch')
        if job['kind'] == 'video':
            _check_video_magic(str(path), 'video/mp4')
        else:
            from PIL import Image
            with Image.open(path) as img:
                media_type = {'JPEG': 'image/jpeg', 'PNG': 'image/png',
                              'WEBP': 'image/webp', 'BMP': 'image/bmp'}.get(img.format)
            _check_image_magic(str(path), media_type)
        local = SimpleNamespace(id=job['id'], kind=job['kind'], path=str(path), stage='loading_models')
        work = asyncio.create_task(run_isolated(local, timeout=60 if job['kind']=='clean' else 300))
        try:
            while not work.done():
                await asyncio.wait({work}, timeout=30)
                response = await client.post(base+'heartbeat', json={**update, 'stage': local.stage})
                response.raise_for_status()
                if response.json()['status'] == 'cancelled':
                    work.cancel()
                    return
            result = await work
            if job['kind'] == 'clean':
                if len(result) > 50_000_000:
                    raise ValueError('PNG export exceeds cloud limit')
                async with httpx.AsyncClient(timeout=60) as storage:
                    response = await storage.put(claim['output_upload']['signed_url'],
                        content=result, headers={'Content-Type': 'image/png'})
                    response.raise_for_status()
                result = {'export': 'metadata_removed'}
            else:
                result.pop('manipulation_heatmap', None)
            response = await client.post(base+'complete', json={**update, 'result': result})
            response.raise_for_status()
        finally:
            if not work.done():
                work.cancel()
            await asyncio.gather(work, return_exceptions=True)


async def drain():
    async with httpx.AsyncClient(base_url=os.environ['MEDIATRUTH_API_URL'], timeout=45,
        headers={'Authorization': 'Bearer '+os.environ['WORKER_SECRET']}) as client:
        while True:
            try:
                response = await client.post('/worker/claim')
                response.raise_for_status()
                claim = response.json()
            except Exception:
                return  # Next real user request can wake the worker again.
            if not claim.get('job'):
                return
            try:
                await process(client, claim)
            except Exception:
                try:
                    await client.post(f"/worker/{claim['job']['id']}/fail",
                                      json={'lease': claim['job']['lease']})
                except Exception:
                    return  # Expired lease will recover on the next claim.


@asynccontextmanager
async def lifespan(app):
    global task
    task = asyncio.create_task(drain())
    yield
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get('/')
async def health():
    return {'status': 'ready', 'busy': bool(task and not task.done())}


@app.post('/wake', status_code=202)
async def wake(request: Request):
    global task
    secret = os.getenv('WORKER_SECRET', '')
    if len(secret) < 32 or not hmac.compare_digest(
            request.headers.get('Authorization', ''), 'Bearer '+secret):
        raise HTTPException(401, 'Invalid worker credential')
    if task is None or task.done():
        task = asyncio.create_task(drain())
    return {'accepted': True}


async def operator_poll():
    """Explicit PC worker session. No system startup task or inbound port needed."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / 'worker.env.local')
    if not os.getenv('MEDIATRUTH_API_URL') or len(os.getenv('WORKER_SECRET', '')) < 32:
        raise SystemExit('Configure MEDIATRUTH_API_URL and WORKER_SECRET in worker.env.local')
    print('MediaTruth worker running. Press Ctrl+C to stop. Polling for actual jobs every 60 seconds.')
    while True:
        await drain()
        await asyncio.sleep(60)


if __name__ == '__main__':
    try:
        asyncio.run(operator_poll())
    except KeyboardInterrupt:
        print('Worker stopped.')
