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


def test_run_serve_sets_graceful_shutdown_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """/_shade/push SSE 常驻不关:默认 timeout_graceful_shutdown=None 会让 Ctrl+C 无限等
    "Waiting for connections to close"(须二次强杀)。spy 断言参数,不起真 server。"""
    from typing import Any

    import uvicorn

    import pyshade.bundler as bundler_mod
    import pyshade.cli as cli_mod
    from pyshade.app import ShadeApp
    from pyshade.bundler import BundleResult
    from pyshade.components import Text
    from pyshade.page import Page
    from pyshade.web import run_serve

    class ServeProbePage(Page):
        hello = Text('serve')

    captured: dict[str, Any] = {}

    def fake_run(app: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    def fake_bundle(app: Any, out_dir: Any, **kwargs: Any) -> BundleResult:
        dist = Path(out_dir)
        dist.mkdir(parents=True, exist_ok=True)
        (dist / 'index.html').write_text('<html></html>', encoding='utf-8')
        return BundleResult(out_dir=dist, app_js_bytes=0, duration_ms=0)

    def fake_load(spec: str) -> ShadeApp:
        return ShadeApp(pages=[ServeProbePage])

    monkeypatch.setattr(uvicorn, 'run', fake_run)
    monkeypatch.setattr(bundler_mod, 'bundle_app', fake_bundle)
    monkeypatch.setattr(cli_mod, 'load_app', fake_load)

    assert run_serve('probe:app', workdir=tmp_path / 'serve') == 0
    assert captured['timeout_graceful_shutdown'] == 3
    assert captured['lifespan'] == 'on'
