"""推送通道:PatchBus 扇出语义 + GET /_shade/push SSE 闭环(dev HTTP 模式验收)。

SSE 是无限流,httpx ASGITransport 会等待应用完整返回(缓冲全量 body)——
因此 SSE 用裸 ASGI 调用驱动,增量收集 http.response.body 事件。
"""

import json
from collections.abc import Generator
from typing import Any

import anyio
import anyio.to_thread
import httpx
import pytest
from httpx import ASGITransport

from pyshade.app import ShadeApp
from pyshade.components import Text
from pyshade.events import EventContext, EventRegistry
from pyshade.page import Page
from pyshade.push import PatchBus, mount_push_route
from pyshade.runtime import build_fastapi_app
from pyshade.state import ServerState, set_dirty_publisher

pytestmark = pytest.mark.anyio


class PushDemoState(ServerState):
    status: str = '空闲'


push_demo = PushDemoState()


class PushPage(Page):
    status = Text(text=PushDemoState.status)


def poke_handler(ctx: EventContext) -> None:
    push_demo.status = '事件内变更'


@pytest.fixture(autouse=True)
def _reset_push_wiring() -> Generator[None, None, None]:
    push_demo.status = '空闲'
    yield
    set_dirty_publisher(None)
    push_demo.status = '空闲'


class TestPatchBus:
    async def test_fanout_to_all_subscribers(self) -> None:
        bus = PatchBus()
        patch = {'target': '$s:X', 'props': {'a': 1}}
        with bus.subscribe() as first, bus.subscribe() as second:
            assert bus.subscriber_count == 2
            bus.publish(patch)
            assert first.receive_nowait() == patch
            assert second.receive_nowait() == patch
        assert bus.subscriber_count == 0

    async def test_slow_subscriber_disconnected_not_dropped(self) -> None:
        # 溢出语义:断流强制重连(丢帧不可静默——丢掉的可能恰是终态帧,前端只在断流时重连)
        bus = PatchBus()
        with bus.subscribe() as receiver:
            for i in range(200):  # 远超缓冲区 64,发布方不得阻塞或抛错
                bus.publish({'target': '$s:X', 'props': {'i': i}})
            assert bus.subscriber_count == 0  # 溢出者已被请出场
            drained: list[dict[str, Any]] = []
            while True:
                try:
                    drained.append(receiver.receive_nowait())
                except anyio.WouldBlock:
                    raise AssertionError("溢出后应收到 EndOfStream(断流),而非静默丢帧后流依旧存活") from None
                except anyio.EndOfStream:
                    break
            assert len(drained) == 64  # 缓冲内已入队消息仍可 drain
            assert drained[0]['props'] == {'i': 0}

    async def test_overflow_then_context_exit_is_safe(self) -> None:
        # 溢出关闭发送端后,subscribe() 上下文正常退出不抛(close 幂等 / remove 防重)
        bus = PatchBus()
        with bus.subscribe():
            for i in range(70):
                bus.publish({'target': '$s:X', 'props': {'i': i}})
        assert bus.subscriber_count == 0

    async def test_sse_generator_terminates_on_overflow(self) -> None:
        # 断流即 SSE 终结:订阅端 async for 收 EndOfStream 正常退出(前端由此触发重连快照)
        bus = PatchBus()
        received: list[dict[str, Any]] = []
        with bus.subscribe() as receiver:
            for i in range(70):
                bus.publish({'target': '$s:X', 'props': {'i': i}})
            async for patch in receiver:
                received.append(patch)
        assert len(received) == 64

    async def test_publish_after_unsubscribe_is_noop(self) -> None:
        bus = PatchBus()
        with bus.subscribe():
            pass
        bus.publish({'target': '$s:X', 'props': {}})  # 不抛错

    async def test_cross_thread_publish_with_subscribers_rejected(self) -> None:
        bus = PatchBus()
        patch: dict[str, Any] = {'target': '$s:X', 'props': {}}
        with bus.subscribe():
            with pytest.raises(RuntimeError, match='事件循环'):
                await anyio.to_thread.run_sync(bus.publish, patch)

    async def test_cross_thread_publish_without_subscribers_tolerated(self) -> None:
        # 启动期主线程写状态是合法惯用法:无订阅者即 no-op,后续订阅经快照收敛
        bus = PatchBus()
        patch: dict[str, Any] = {'target': '$s:X', 'props': {}}
        await anyio.to_thread.run_sync(bus.publish, patch)


def _build_app() -> Any:
    app = ShadeApp(pages=[PushPage])
    registry = EventRegistry.from_app(app, extra_handlers={'poke': poke_handler})
    return build_fastapi_app(registry)


def _events_from(chunks: list[bytes]) -> list[dict[str, Any]]:
    text = b''.join(chunks).decode('utf-8')
    events: list[dict[str, Any]] = []
    for raw in text.split('\n\n'):
        if raw.startswith('data: '):
            events.append(json.loads(raw[len('data: ') :]))
    return events


class TestPushSse:
    async def test_snapshot_first_then_live_patch(self) -> None:
        fastapi_app = _build_app()
        chunks: list[bytes] = []
        status_holder: list[int] = []

        scope: dict[str, Any] = {
            'type': 'http',
            'asgi': {'version': '3.0', 'spec_version': '2.3'},
            'http_version': '1.1',
            'method': 'GET',
            'scheme': 'http',
            'path': '/_shade/push',
            'raw_path': b'/_shade/push',
            'query_string': b'',
            'headers': [],
            'client': ('127.0.0.1', 1),
            'server': ('testserver', 80),
            'root_path': '',
        }

        async def receive() -> dict[str, Any]:
            await anyio.sleep_forever()
            raise AssertionError('unreachable')

        async def send(message: dict[str, Any]) -> None:
            if message['type'] == 'http.response.start':
                status_holder.append(int(message['status']))
            elif message['type'] == 'http.response.body':
                chunks.append(bytes(message.get('body', b'')))

        async with anyio.create_task_group() as tg:
            tg.start_soon(fastapi_app, scope, receive, send)

            with anyio.fail_after(5):
                while len(_events_from(chunks)) < 1:
                    await anyio.sleep(0.01)
            assert status_holder == [200]
            snapshot = _events_from(chunks)[0]
            ours = [p for p in snapshot['patches'] if p['target'] == '$s:PushDemoState']
            assert ours == [{'target': '$s:PushDemoState', 'props': {'status': '空闲'}}]

            # 请求外变更(无活跃 sink)→ publisher → bus → 实时帧
            push_demo.status = '后台变更'
            with anyio.fail_after(5):
                while len(_events_from(chunks)) < 2:
                    await anyio.sleep(0.01)
            live = _events_from(chunks)[1]
            assert live['patches'] == [{'target': '$s:PushDemoState', 'props': {'status': '后台变更'}}]

            tg.cancel_scope.cancel()

    async def test_event_handler_diff_not_double_pushed(self) -> None:
        # 事件内变更走响应 envelope(活跃 sink),不进推送通道
        fastapi_app = _build_app()
        bus = mount_push_route(fastapi_app, bus=PatchBus())  # 重新接线拿到 bus 引用

        transport = ASGITransport(app=fastapi_app)
        with bus.subscribe() as receiver:
            async with httpx.AsyncClient(transport=transport, base_url='http://t') as client:
                response = await client.post('/_shade/event/poke', json={})
            assert response.json()['patches'] == [{'target': '$s:PushDemoState', 'props': {'status': '事件内变更'}}]
            with pytest.raises(anyio.WouldBlock):
                receiver.receive_nowait()
