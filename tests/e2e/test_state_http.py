"""ServerState auto-diff 的 HTTP E2E:事件响应 envelope = sink patches + 显式 Update。

M0 兼容:不碰 ServerState 的 handler,envelope 与 M0 完全一致。
"""

import httpx
import pytest
from httpx import ASGITransport

from pyshade.app import ShadeApp
from pyshade.components import Text
from pyshade.events import EventContext, EventRegistry, Update
from pyshade.page import Page
from pyshade.runtime import build_fastapi_app
from pyshade.state import ServerState

pytestmark = pytest.mark.anyio


class E2eChatState(ServerState):
    status: str = '就绪'
    round_count: int = 0


e2e_chat = E2eChatState()


class StatePage(Page):
    status = Text(text=E2eChatState.status)
    plain = Text('普通文本')


def auto_diff_handler(ctx: EventContext) -> None:
    e2e_chat.status = '思考中'
    e2e_chat.round_count = e2e_chat.round_count + 1


def mixed_handler(ctx: EventContext) -> list[Update]:
    e2e_chat.status = 'auto 值'
    return [Update(StatePage.plain, text='显式 Update')]


async def legacy_handler(ctx: EventContext) -> list[Update]:
    return [Update(StatePage.plain, text='M0 风格')]


def _build_client() -> httpx.AsyncClient:
    app = ShadeApp(pages=[StatePage])
    registry = EventRegistry.from_app(
        app,
        extra_handlers={'auto_diff': auto_diff_handler, 'mixed': mixed_handler, 'legacy': legacy_handler},
    )
    fastapi_app = build_fastapi_app(registry)
    return httpx.AsyncClient(transport=ASGITransport(app=fastapi_app), base_url='http://testserver')


async def test_auto_diff_envelope() -> None:
    before = e2e_chat.round_count
    async with _build_client() as client:
        response = await client.post('/_shade/event/auto_diff', json={})
    assert response.status_code == 200
    patches = response.json()['patches']
    assert patches == [{'target': '$s:E2eChatState', 'props': {'status': '思考中', 'round_count': before + 1}}]


async def test_auto_diff_before_explicit_update() -> None:
    async with _build_client() as client:
        response = await client.post('/_shade/event/mixed', json={})
    patches = response.json()['patches']
    assert patches[0]['target'] == '$s:E2eChatState'
    assert patches[1] == {'target': 'StatePage.plain', 'props': {'text': '显式 Update'}}


async def test_m0_handler_envelope_unchanged() -> None:
    async with _build_client() as client:
        response = await client.post('/_shade/event/legacy', json={})
    assert response.json() == {'patches': [{'target': 'StatePage.plain', 'props': {'text': 'M0 风格'}}]}


async def test_sink_isolated_between_requests() -> None:
    async with _build_client() as client:
        await client.post('/_shade/event/auto_diff', json={})
        response = await client.post('/_shade/event/legacy', json={})
    # 第二个请求不携带第一个请求的 auto-diff 残留
    assert response.json()['patches'] == [{'target': 'StatePage.plain', 'props': {'text': 'M0 风格'}}]
