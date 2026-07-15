"""EventContext.value 数值保真:Slider onValueCommit 的 JSON number 必须以 int/float 落地。

协议面(JSON → FastAPI → EventContext)与 IPC 模式完全同路(同一 bridge/FastAPI 解析),
HTTP 层验证即覆盖跨界类型保真。
"""

import httpx
import pytest
from httpx import ASGITransport

from pyshade.app import ShadeApp
from pyshade.components import Slider
from pyshade.events import EventContext, EventRegistry
from pyshade.page import Page
from pyshade.runtime import build_fastapi_app

pytestmark = pytest.mark.anyio

received: list[object] = []


def on_volume_change(ctx: EventContext) -> None:
    received.append(ctx.value)


class VolumePage(Page):
    volume = Slider(label='音量', on_change=on_volume_change)


def _client() -> httpx.AsyncClient:
    app = ShadeApp(pages=[VolumePage])
    registry = EventRegistry.from_app(app)
    return httpx.AsyncClient(transport=ASGITransport(app=build_fastapi_app(registry)), base_url='http://t')


async def test_integer_value_stays_int() -> None:
    received.clear()
    async with _client() as client:
        response = await client.post('/_shade/event/VolumePage.volume.on_change', json={'value': 42})
    assert response.status_code == 200
    assert received == [42]
    assert type(received[0]) is int


async def test_float_value_stays_float() -> None:
    received.clear()
    async with _client() as client:
        response = await client.post('/_shade/event/VolumePage.volume.on_change', json={'value': 2.5})
    assert response.status_code == 200
    assert received == [2.5]
    assert type(received[0]) is float


async def test_bool_value_not_coerced_to_number() -> None:
    received.clear()
    async with _client() as client:
        await client.post('/_shade/event/VolumePage.volume.on_change', json={'value': True})
    assert received == [True]
    assert type(received[0]) is bool
