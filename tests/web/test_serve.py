"""pyshade serve 的生产 dispatcher(M4 web target):静态与 /_shade/* 二路分发。"""

from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from pyshade.events import EventRegistry
from pyshade.runtime import build_fastapi_app
from pyshade.web import make_web_asgi

pytestmark = pytest.mark.anyio


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<html><body>shade-index</body></html>', encoding='utf-8')
    (dist / 'style.css').write_text(':root {}', encoding='utf-8')
    return dist


def _client(tmp_path: Path) -> httpx.AsyncClient:
    fastapi_app = build_fastapi_app(EventRegistry({}))
    dispatcher = make_web_asgi(fastapi_app, _dist(tmp_path))
    return httpx.AsyncClient(transport=ASGITransport(app=dispatcher), base_url='http://serve')


async def test_root_serves_index(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        response = await client.get('/')
        assert response.status_code == 200
        assert 'shade-index' in response.text


async def test_static_asset(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        response = await client.get('/style.css')
        assert response.status_code == 200


async def test_shade_namespace_forwarded(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        response = await client.post('/_shade/event/nope', json={})
        assert response.status_code == 404  # 用户 app 的 unknown-handler 语义,而非静态 404
        assert 'unknown handler' in response.text


async def test_docs_routes_absent(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        for path in ('/docs', '/openapi.json'):
            response = await client.get(path)
            assert response.status_code == 404
