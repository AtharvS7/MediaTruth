import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.jobs import Job, JobManager, QueueFull, run_isolated
from api.routes.job_routes import router
from utils.auth import get_current_user


@pytest.mark.asyncio
async def test_queue_bounded_and_cancel_removes_uploads(tmp_path):
    active = asyncio.Event()
    async def runner(job):
        active.set()
        await asyncio.Event().wait()
    manager = JobManager(runner=runner)
    paths = [tmp_path / str(index) for index in range(4)]
    for path in paths:
        path.write_bytes(b'fixture')
    first = manager.submit('a', 'image', str(paths[0]), 'a.png')
    await active.wait()
    manager.submit('b', 'image', str(paths[1]), 'b.png')
    manager.submit('c', 'image', str(paths[2]), 'c.png')
    with pytest.raises(QueueFull):
        manager.submit('d', 'image', str(paths[3]), 'd.png')
    await manager.cancel(first)
    assert first.status == 'cancelled'
    assert not paths[0].exists()
    await manager.close()
    assert not paths[1].exists() and not paths[2].exists()


@pytest.mark.asyncio
async def test_finished_job_saved_once_and_source_removed(tmp_path):
    path = tmp_path / 'image'
    path.write_bytes(b'fixture')
    database = SimpleNamespace(save_scan=AsyncMock())
    manager = JobManager(runner=AsyncMock(return_value={'final_verdict': 'Inconclusive'}),
                         database_factory=lambda: database)
    job = manager.submit('owner', 'image', str(path), 'x.png')
    await job.task
    assert job.status == 'completed'
    database.save_scan.assert_awaited_once()
    assert len(database.save_scan.call_args.args[-1]) == 64
    assert not path.exists()


@pytest.mark.asyncio
async def test_timeout_kills_real_process_before_return(tmp_path, monkeypatch):
    original = asyncio.create_subprocess_exec
    processes = []
    async def create(*args, **kwargs):
        process = await original(sys.executable, '-c', 'import time; time.sleep(60)', **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', create)
    with pytest.raises(TimeoutError):
        await run_isolated(Job('id', 'owner', 'image', str(tmp_path / 'unused'), 'x.png'), timeout=.1)
    assert processes and processes[0].returncode is not None


def test_other_owner_cannot_read_or_cancel_job():
    app = FastAPI()
    job = Job('id', 'owner-a', 'image', 'private-path', 'private-filename')
    app.state.jobs = SimpleNamespace(jobs={'id': job})
    app.include_router(router, prefix='/jobs')
    app.dependency_overrides[get_current_user] = lambda: {'id': 'owner-b'}
    client = TestClient(app)
    assert client.get('/jobs/id').status_code == 404
    assert client.delete('/jobs/id').status_code == 404


def test_upload_job_completes_and_persists_report(tmp_path, monkeypatch):
    import io
    import time
    from PIL import Image
    from api.routes.job_routes import limiter
    app = FastAPI()
    database = SimpleNamespace(save_scan=AsyncMock())
    app.state.jobs = JobManager(runner=AsyncMock(return_value={'final_verdict': 'Inconclusive'}),
                                database_factory=lambda: database)
    app.state.limiter = limiter
    app.include_router(router, prefix='/jobs')
    app.dependency_overrides[get_current_user] = lambda: {'id': 'job-owner'}
    monkeypatch.setattr('utils.file_utils.TEMP_DIR', tmp_path)
    media = io.BytesIO()
    Image.new('RGB', (8, 8)).save(media, format='PNG')
    with TestClient(app) as client:
        response = client.post('/jobs', files={'file': ('x.png', media.getvalue(), 'image/png')})
        assert response.status_code == 202
        job_id = response.json()['id']
        for _ in range(100):
            response = client.get('/jobs/' + job_id)
            if response.json()['status'] == 'completed':
                break
            time.sleep(.01)
        assert response.json()['result']['scan_id'] == job_id
        database.save_scan.assert_awaited_once()
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_cancel_kills_real_process(tmp_path, monkeypatch):
    original = asyncio.create_subprocess_exec
    launched = asyncio.Event()
    processes = []
    async def create(*args, **kwargs):
        process = await original(sys.executable, '-c', 'import time; time.sleep(60)', **kwargs)
        processes.append(process)
        launched.set()
        return process
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', create)
    task = asyncio.create_task(run_isolated(Job('id', 'owner', 'image', 'unused', 'x.png')))
    await launched.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert processes[0].returncode is not None
