"""服务端 Navigate 的 HTTP E2E(M2 Phase 5):envelope 编码为 $nav patch,未知目标 500。"""

import httpx
import pytest
from httpx import ASGITransport

from pyshade.app import ShadeApp
from pyshade.components import Text
from pyshade.events import EventContext, EventRegistry, Update
from pyshade.nav import Navigate
from pyshade.page import Page
from pyshade.runtime import build_fastapi_app

pytestmark = pytest.mark.anyio


class NavHttpHomePage(Page):
    banner = Text('主页')


class NavHttpDetailPage(Page):
    info = Text('详情')


def goto_detail(ctx: EventContext) -> list[Navigate]:
    return [Navigate(NavHttpDetailPage)]


def update_then_navigate(ctx: EventContext) -> list[Update | Navigate]:
    return [Update(NavHttpDetailPage.info, text='已更新'), Navigate('NavHttpDetailPage')]


def goto_unknown(ctx: EventContext) -> list[Navigate]:
    return [Navigate('OrphanPage')]


def _build_client() -> httpx.AsyncClient:
    app = ShadeApp(pages=[NavHttpHomePage, NavHttpDetailPage])
    registry = EventRegistry.from_app(
        app,
        extra_handlers={
            'goto_detail': goto_detail,
            'update_then_navigate': update_then_navigate,
            'goto_unknown': goto_unknown,
        },
    )
    fastapi_app = build_fastapi_app(registry)
    return httpx.AsyncClient(transport=ASGITransport(app=fastapi_app), base_url='http://testserver')


async def test_navigate_encoded_as_nav_patch() -> None:
    async with _build_client() as client:
        response = await client.post('/_shade/event/goto_detail', json={})
    assert response.status_code == 200
    assert response.json() == {'patches': [{'target': '$nav', 'props': {'page': 'NavHttpDetailPage'}}]}


async def test_update_and_navigate_same_envelope() -> None:
    async with _build_client() as client:
        response = await client.post('/_shade/event/update_then_navigate', json={})
    assert response.status_code == 200
    patches = response.json()['patches']
    assert patches == [
        {'target': 'NavHttpDetailPage.info', 'props': {'text': '已更新'}},
        {'target': '$nav', 'props': {'page': 'NavHttpDetailPage'}},
    ]


async def test_unknown_navigate_target_rejected() -> None:
    async with _build_client() as client:
        response = await client.post('/_shade/event/goto_unknown', json={})
    assert response.status_code == 500
    assert "Navigate 目标 'OrphanPage'" in response.json()['detail']
