"""Each 模板事件的 HTTP E2E(M2 Phase 6):item_index/item_key 回传 + 整表替换 auto-diff。"""

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from pydantic import BaseModel

from pyshade.app import ShadeApp
from pyshade.components import Button, Card, Each, Text
from pyshade.events import EventContext, EventRegistry
from pyshade.page import Page
from pyshade.runtime import build_fastapi_app
from pyshade.state import ServerState

pytestmark = pytest.mark.anyio


class EachHttpMessage(BaseModel):
    id: int
    text: str


class EachHttpState(ServerState):
    messages: list[EachHttpMessage] = [
        EachHttpMessage(id=1, text='第一条'),
        EachHttpMessage(id=2, text='第二条'),
    ]


each_http_state = EachHttpState()

_received: list[EventContext] = []


def on_recall(ctx: EventContext) -> None:
    _received.append(ctx)
    # 惯用法:整表替换驱动 auto-diff(原地 append 不触发描述符赋值)
    each_http_state.messages = [m for m in each_http_state.messages if m.id != ctx.item_key]


def _message_template(m: Any) -> Card:
    return Card(Text(m.text), Button('撤回', on_click=on_recall), title='消息')


class EachHttpPage(Page):
    messages = Each(EachHttpState.messages, render=_message_template, key='id')


def _build_client() -> httpx.AsyncClient:
    app = ShadeApp(pages=[EachHttpPage])
    registry = EventRegistry.from_app(app)
    fastapi_app = build_fastapi_app(registry)
    return httpx.AsyncClient(transport=ASGITransport(app=fastapi_app), base_url='http://testserver')


async def test_template_event_carries_item_index_and_key() -> None:
    _received.clear()
    async with _build_client() as client:
        response = await client.post(
            '/_shade/event/EachHttpPage.messages.$t[0][1].on_click',
            json={'item_index': 1, 'item_key': 2},
        )
    assert response.status_code == 200
    assert _received[0].item_index == 1
    assert _received[0].item_key == 2
    # auto-diff:整表替换以列表值出现在 $s: patch 中
    patches = response.json()['patches']
    assert patches == [{'target': '$s:EachHttpState', 'props': {'messages': [{'id': 1, 'text': '第一条'}]}}]
