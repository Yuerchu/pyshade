"""E2E 测试:通过真 HTTP 请求验证事件路由全链路(不需浏览器/WebView)。

用 httpx AsyncClient + ASGITransport 直接打 FastAPI app,
验证 example 的 pages/handlers/EventRegistry → 路由 → patches 响应完整闭环。
"""

import httpx
import pytest
from httpx import ASGITransport
from login_form.app import app
from login_form.handlers import bench_echo

from pyshade.events import EventRegistry
from pyshade.runtime import build_fastapi_app

pytestmark = pytest.mark.anyio


def _build_client() -> httpx.AsyncClient:
    registry = EventRegistry.from_app(app, extra_handlers={'bench_echo': bench_echo})
    fastapi_app = build_fastapi_app(registry, title=app.title)
    transport = ASGITransport(app=fastapi_app)  # pyright: ignore[reportArgumentType]
    return httpx.AsyncClient(transport=transport, base_url='http://testserver')


async def test_submit_with_credentials() -> None:
    async with _build_client() as client:
        resp = await client.post(
            '/_shade/event/LoginPage.submit.on_click',
            json={'values': {'username': 'yuerchu', 'password': 's3cret'}},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data['patches']) == 1
    patch = data['patches'][0]
    assert patch['target'] == 'LoginPage.greeting'
    assert '你好,yuerchu' in patch['props']['text']
    assert '6' in patch['props']['text']


async def test_submit_empty_fields() -> None:
    async with _build_client() as client:
        resp = await client.post(
            '/_shade/event/LoginPage.submit.on_click',
            json={'values': {}},
        )
    assert resp.status_code == 200
    patch = resp.json()['patches'][0]
    assert '不能为空' in patch['props']['text']


async def test_change_event_returns_empty_patches() -> None:
    async with _build_client() as client:
        resp = await client.post(
            '/_shade/event/LoginPage.username.on_change',
            json={'value': 'test_user'},
        )
    assert resp.status_code == 200
    assert resp.json() == {'patches': []}


async def test_remember_toggle() -> None:
    async with _build_client() as client:
        resp = await client.post(
            '/_shade/event/LoginPage.remember.on_change',
            json={'value': True},
        )
    assert resp.status_code == 200
    assert resp.json() == {'patches': []}


async def test_bench_echo() -> None:
    async with _build_client() as client:
        resp = await client.post('/_shade/event/bench_echo', json={})
    assert resp.status_code == 200
    assert resp.json() == {'patches': []}


async def test_unknown_handler_404() -> None:
    async with _build_client() as client:
        resp = await client.post('/_shade/event/nope.nope', json={})
    assert resp.status_code == 404


async def test_invalid_payload_422() -> None:
    async with _build_client() as client:
        resp = await client.post(
            '/_shade/event/LoginPage.submit.on_click',
            json={'values': 'not_a_dict'},
        )
    assert resp.status_code == 422


async def test_no_docs_endpoints() -> None:
    async with _build_client() as client:
        for path in ['/docs', '/redoc', '/openapi.json']:
            resp = await client.get(path)
            assert resp.status_code == 404, f'{path} should be disabled'


async def test_password_not_in_non_submit_event() -> None:
    """安全默认验证:非 submit 事件的 payload 不含 password(前端层保证,这里验证后端能正常处理)。"""
    async with _build_client() as client:
        resp = await client.post(
            '/_shade/event/LoginPage.username.on_change',
            json={'values': {'username': 'x'}, 'value': 'x'},
        )
    assert resp.status_code == 200
