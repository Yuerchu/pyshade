"""dev dispatcher:四路分发、SSE 首帧 generation、client 注入幂等(不起 uvicorn 不联网)。"""

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest
from httpx import ASGITransport

from pyshade.asgi._types import Receive, Scope, Send
from pyshade.dev._server import DEV_CLIENT_JS, inject_dev_client, make_dev_asgi

pytestmark = pytest.mark.anyio


async def _echo_user_app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return
    else:
        body = f'user-app:{scope["path"]}'.encode()
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': body})


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<html><head></head><body>ok</body></html>', encoding='utf-8')
    (dist / 'app.js').write_text('// app', encoding='utf-8')
    return dist


class TestDispatcher:
    async def test_client_js_served(self, tmp_path: Path) -> None:
        app = make_dev_asgi(_echo_user_app, _make_dist(tmp_path), 'gen-1')
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://dev') as client:
            response = await client.get('/_shade/dev/client.js')
        assert response.status_code == 200
        assert response.text == DEV_CLIENT_JS

    async def test_shade_routes_forwarded_to_user_app(self, tmp_path: Path) -> None:
        app = make_dev_asgi(_echo_user_app, _make_dist(tmp_path), 'gen-1')
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://dev') as client:
            response = await client.post('/_shade/event/X.y.on_click')
        assert response.text == 'user-app:/_shade/event/X.y.on_click'

    async def test_static_fallback_serves_index(self, tmp_path: Path) -> None:
        app = make_dev_asgi(_echo_user_app, _make_dist(tmp_path), 'gen-1')
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://dev') as client:
            index = await client.get('/')
            asset = await client.get('/app.js')
        assert 'ok' in index.text
        assert asset.text == '// app'

    async def test_sse_first_frame_carries_generation(self, tmp_path: Path) -> None:
        # ASGITransport 会缓冲无限 SSE(M1 教训):原始 ASGI 驱动,收到首帧即断连
        app = make_dev_asgi(_echo_user_app, _make_dist(tmp_path), 'gen-abc')
        scope: dict[str, Any] = {'type': 'http', 'method': 'GET', 'path': '/_shade/dev/events', 'headers': []}
        received: list[MutableMapping[str, Any]] = []
        got_first = anyio.Event()

        async def receive() -> 'MutableMapping[str, Any]':
            await got_first.wait()
            return {'type': 'http.disconnect'}

        async def send(message: 'MutableMapping[str, Any]') -> None:
            received.append(message)
            if message['type'] == 'http.response.body' and b'generation' in message.get('body', b''):
                got_first.set()

        with anyio.fail_after(5):
            await app(scope, receive, send)
        bodies = b''.join(m.get('body', b'') for m in received if m['type'] == 'http.response.body')
        assert b'data: {"generation": "gen-abc"}' in bodies


class TestInjectClient:
    def test_injects_before_head_close(self) -> None:
        html = '<html><head><title>x</title></head><body></body></html>'
        out = inject_dev_client(html)
        assert '<script src="/_shade/dev/client.js"></script>' in out
        assert out.index('client.js') < out.index('</head>')

    def test_idempotent(self) -> None:
        once = inject_dev_client('<html><head></head></html>')
        assert inject_dev_client(once) == once
