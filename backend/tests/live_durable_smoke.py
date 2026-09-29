"""Explicit live smoke: temporary confirmed users, private media, then cleanup.

Run from backend: python tests/live_durable_smoke.py
No email is sent. Never run automatically in CI. Credentials come from .env.
"""
import asyncio
import hashlib
import io
import os
from pathlib import Path
import secrets
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
os.environ['JOB_BACKEND'] = 'supabase'

import httpx
from PIL import Image
from supabase import create_client
from main import app
from services.remote_worker import process


async def main():
    client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
    users, jobs = [], []
    worker = {'Authorization': 'Bearer '+os.environ['WORKER_SECRET']}
    try:
        headers = []
        for _ in range(2):
            email = f'mediatruth-test-{uuid.uuid4()}@example.invalid'
            password = secrets.token_urlsafe(32)
            created = client.auth.admin.create_user({'email': email, 'password': password,
                                                     'email_confirm': True})
            users.append(created.user.id)
            # Separate client so admin persistence credentials are never replaced by a user session.
            auth = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
            session = auth.auth.sign_in_with_password({'email': email, 'password': password}).session
            headers.append({'Authorization': 'Bearer '+session.access_token})
        image = io.BytesIO()
        Image.new('RGBA', (8, 8), (10, 20, 30, 128)).save(image, format='PNG')
        content = image.getvalue()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                    base_url='http://testserver', timeout=60) as api:
            assert (await api.post('/worker/claim', headers=worker)).status_code == 200
            for kind in ('clean', 'image'):
                body = {'kind': kind, 'filename': 'fixture.png', 'byte_size': len(content),
                        'input_sha256': hashlib.sha256(content).hexdigest(),
                        'idempotency_key': str(uuid.uuid4())}
                response = await api.post('/uploads', json=body, headers=headers[0])
                assert response.status_code == 201, 'Reservation failed'
                data = response.json()
                job_id = data['job']['id']
                jobs.append(job_id)
                duplicate = await api.post('/uploads', json=body, headers=headers[0])
                assert duplicate.json()['job']['id'] == job_id, 'Duplicate reservation'
                async with httpx.AsyncClient(timeout=30) as storage:
                    uploaded = await storage.put(data['upload']['signed_url'], content=content,
                                                  headers={'Content-Type': 'image/png'})
                    assert uploaded.is_success, 'Signed upload failed'
                response = await api.post(f'/uploads/{job_id}/finalize', headers=headers[0])
                assert response.status_code == 202, 'Finalize failed'
                assert (await api.get(f'/jobs/{job_id}', headers=headers[1])).status_code == 404, 'Cross-owner job access'
                assert (await api.post('/worker/claim')).status_code == 401, 'Unauthenticated worker access'
                claim = (await api.post('/worker/claim', headers=worker)).json()
                assert claim['job']['id'] == job_id, 'Claim mismatch'
                if kind == 'clean':
                    # Real isolated cleaner, signed output upload and lease-fenced completion.
                    api.headers.update(worker)
                    await process(api, claim)
                    api.headers.pop('Authorization', None)
                    download = await api.get(f'/jobs/{job_id}/download', headers=headers[0])
                    assert download.status_code == 200, 'Export download missing'
                    async with httpx.AsyncClient(timeout=30) as storage:
                        result = await storage.get(download.json()['url'])
                    with Image.open(io.BytesIO(result.content)) as cleaned:
                        assert cleaned.getpixel((0, 0)) == (10, 20, 30, 128), 'Export pixels changed'
                else:
                    response = await api.post(f'/worker/{job_id}/complete', headers=worker,
                        json={'lease': claim['job']['lease'], 'result': {
                            'final_verdict': 'AI Generated', 'confidence': .99}})
                    assert response.status_code == 200, 'Atomic report completion failed'
                    assert response.json()['result']['final_verdict'] == 'Inconclusive', 'Verdict not gated'
                    assert (await api.get(f'/scan/{job_id}', headers=headers[0])).status_code == 200, 'Owner report missing'
                    assert (await api.get(f'/scan/{job_id}', headers=headers[1])).status_code in (403,404), 'Cross-owner report access'
            print('PASS: live login, signed uploads, duplicate requests, isolation, real PNG export, atomic report')
    finally:
        for job_id in jobs:
            owner = users[0]
            client.storage.from_('mediatruth-jobs').remove([f'{owner}/{job_id}/input',
                                                          f'{owner}/{job_id}/output.png'])
            client.table('media_jobs').delete().eq('id', job_id).execute()
            client.table('scans').delete().eq('id', job_id).execute()
        for user_id in users:
            client.auth.admin.delete_user(user_id)
        print('Temporary test users and data removed')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as exc:
        # Exceptions from storage can contain signed URLs; never print their bodies.
        print('FAIL:', type(exc).__name__, str(exc) if isinstance(exc, AssertionError) else '')
        raise SystemExit(1)
