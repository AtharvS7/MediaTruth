"""Worker boundary tests: untrusted storage bytes never bypass validation."""
import asyncio
import hashlib
import io
from unittest.mock import AsyncMock

import httpx
from PIL import Image
import pytest

from services import remote_worker


def fixture(monkeypatch, data, *, digest=None, size=None, cancelled=False):
    requests = []
    real_client = httpx.AsyncClient

    def storage(request):
        requests.append(request)
        return httpx.Response(200, content=data)

    monkeypatch.setattr(remote_worker.httpx, 'AsyncClient',
        lambda **kwargs: real_client(transport=httpx.MockTransport(storage), **kwargs))
    api = AsyncMock()
    api.post.return_value = httpx.Response(200, json={'status': 'cancelled' if cancelled else 'running'},
        request=httpx.Request('POST', 'https://api.invalid/worker'))
    worker = AsyncMock(return_value=b'export')
    monkeypatch.setattr(remote_worker, 'run_isolated', worker)
    claim = {'job': {'id': 'test', 'lease': 'lease', 'kind': 'clean',
        'byte_size': len(data) if size is None else size,
        'input_sha256': digest or hashlib.sha256(data).hexdigest()},
        'download_url': 'https://storage.invalid/input?token=private',
        'output_upload': {'signed_url': 'https://storage.invalid/output?token=private'}}
    return api, worker, claim, requests


def png():
    data = io.BytesIO()
    Image.new('RGB', (4, 4)).save(data, format='PNG')
    return data.getvalue()


@pytest.mark.parametrize('case', ['digest', 'size', 'malformed'])
def test_invalid_input_never_reaches_inference(monkeypatch, case):
    data = b'not an image' if case == 'malformed' else png()
    api, worker, claim, _ = fixture(monkeypatch, data,
        digest='0'*64 if case == 'digest' else None,
        size=1 if case == 'size' else None)
    with pytest.raises((ValueError, OSError)):
        asyncio.run(remote_worker.process(api, claim))
    worker.assert_not_called()
    api.post.assert_not_called()


@pytest.mark.parametrize('cancelled', [False, True])
def test_export_and_cancellation_do_not_leak_worker_credentials(monkeypatch, cancelled):
    api, worker, claim, requests = fixture(monkeypatch, png(), cancelled=cancelled)
    monkeypatch.setenv('WORKER_SECRET', 'private-worker-secret')
    asyncio.run(remote_worker.process(api, claim))
    assert all('authorization' not in request.headers for request in requests)
    completions = [call for call in api.post.call_args_list if call.args[0].endswith('/complete')]
    assert len(completions) == (0 if cancelled else 1)
    assert [r.method for r in requests] == (['GET'] if cancelled else ['GET', 'PUT'])
