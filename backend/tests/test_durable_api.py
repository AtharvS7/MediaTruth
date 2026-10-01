from unittest.mock import AsyncMock
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.routes.durable_routes import router, coordinator
from utils.auth import get_current_user
from utils.intake import MediaIntakeMiddleware


def setup(monkeypatch):
    monkeypatch.setenv('WORKER_SECRET', 'x'*48)
    app = FastAPI()
    app.add_middleware(MediaIntakeMiddleware)
    app.include_router(router)
    db = SimpleNamespace(call=AsyncMock(), cleanup=AsyncMock(), upload_url=AsyncMock(),
                         check_object=AsyncMock(), checkin=AsyncMock(), worker_online=AsyncMock(return_value=True))
    db.download_url = AsyncMock(return_value='https://storage.invalid/export')
    app.dependency_overrides[coordinator] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {'id': str(uuid4())}
    return TestClient(app), db


def test_worker_auth_and_body_bounds(monkeypatch):
    client, db = setup(monkeypatch)
    assert client.post('/worker/claim').status_code == 401
    assert client.post('/worker/claim', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    assert client.post('/worker/claim', content=b'x'*600001).status_code == 413
    db.call.assert_not_called()


def test_invalid_reservation_never_reaches_database(monkeypatch):
    client, db = setup(monkeypatch)
    response = client.post('/uploads', json={'kind': 'image', 'filename': 'a.png',
        'byte_size': 50000001, 'input_sha256': 'a'*64, 'idempotency_key': str(uuid4())})
    assert response.status_code == 422
    db.call.assert_not_called()


def test_worker_cannot_select_export_mode_for_an_image(monkeypatch):
    client, db = setup(monkeypatch)
    identity = str(uuid4())
    db.call.side_effect = [dict(kind='image'), dict(id=identity, kind='image', status='completed',
        result={'final_verdict': 'Inconclusive'})]
    response = client.post(f'/worker/{identity}/complete', headers={'Authorization': 'Bearer '+'x'*48},
        json={'lease': str(uuid4()), 'result': {'export': 'metadata_removed', 'confidence': .99}})
    assert response.status_code == 200
    assert db.call.call_args.kwargs['result']['final_verdict'] == 'Inconclusive'
    assert db.call.call_args.kwargs['result']['confidence'] == 0


@pytest.mark.parametrize('age_hours,expected', [(23, 200), (25, 404)])
def test_export_expiry_does_not_depend_on_cleanup(monkeypatch, age_hours, expected):
    client, db = setup(monkeypatch)
    identity = str(uuid4())
    db.call.return_value = dict(id=identity, kind='clean', status='completed',
        output_deleted=False,
        created_at=(datetime.now(timezone.utc)-timedelta(hours=age_hours)).isoformat())
    response = client.get(f'/jobs/{identity}/download')
    assert response.status_code == expected
    assert db.download_url.await_count == (1 if expected == 200 else 0)


def test_offline_worker_does_not_reserve_storage(monkeypatch):
    client, db = setup(monkeypatch)
    db.worker_online.return_value = False
    monkeypatch.setenv('WORKER_URL', '')
    response = client.post('/uploads', json={'kind': 'image', 'filename': 'a.png',
        'byte_size': 100, 'input_sha256': 'a'*64, 'idempotency_key': str(uuid4())})
    assert response.status_code == 503
    db.call.assert_not_called()
    db.upload_url.assert_not_called()
