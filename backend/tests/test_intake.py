import asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from utils.intake import MediaIntakeMiddleware


def test_rejects_declared_oversize_without_reading_body():
    app = FastAPI()
    app.add_middleware(MediaIntakeMiddleware)
    response = TestClient(app).post('/image/analyze', headers={'Content-Length': str(60 * 1024**2)})
    assert response.status_code == 413


def test_rejects_actual_chunked_oversize():
    app = FastAPI()
    app.add_middleware(MediaIntakeMiddleware)

    @app.post('/image/analyze')
    async def upload(request: Request):
        async for _ in request.stream():
            pass
        return {}

    async def run():
        responses = []
        async def receive():
            return {'type': 'http.request', 'body': b'x' * 1024**2, 'more_body': True}
        async def send(message):
            responses.append(message)
        await app({'type': 'http', 'method': 'POST', 'path': '/image/analyze',
                   'headers': [], 'query_string': b''}, receive, send)
        assert responses[0]['status'] == 413
    asyncio.run(run())
