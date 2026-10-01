from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.routes import health_routes


@pytest.mark.parametrize('state,code', [(True, 200), (False, 503), (RuntimeError('private'), 503)])
def test_cloud_readiness_requires_available_worker(monkeypatch, state, code):
    monkeypatch.setenv('JOB_BACKEND', 'supabase')
    check = AsyncMock(side_effect=state) if isinstance(state, Exception) else AsyncMock(return_value=state)
    monkeypatch.setattr('services.durable_jobs.DurableJobs', lambda: SimpleNamespace(worker_online=check))
    app = FastAPI()
    app.include_router(health_routes.router, prefix='/health')
    app.state.model_loader = SimpleNamespace(ready=True)
    response = TestClient(app).get('/health/ready')
    assert response.status_code == code
    assert response.json() == {'ready': code == 200}
    assert TestClient(app).get('/health/').status_code == 200
