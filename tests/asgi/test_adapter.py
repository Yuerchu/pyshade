import json
import threading
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

import anyio
import pytest
from anyio.from_thread import start_blocking_portal
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from pyshade.asgi._adapter import AsgiIpcAdapter
from pyshade.asgi._lifespan import LifespanError
from pyshade.asgi._types import ChannelLike
from pyshade.asgi._wire import decode_envelope
from tests.asgi.fakes import FakeChannel, FakeInvoke, FakeResolver, make_invoke


def _wait_for(predicate: Callable[[], object], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met within timeout")


def _fake_channel_factory(channel_id: str, webview_window: Any) -> ChannelLike:
    return FakeChannel()


def _build_app(events: list[str]) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        events.append('startup')
        yield
        events.append('shutdown')

    app = FastAPI(lifespan=lifespan)

    @app.get('/ping')
    async def ping() -> dict[str, bool]:
        return {'pong': True}

    return app


def test_full_cycle_and_ready_gate() -> None:
    events: list[str] = []
    app = _build_app(events)
    with start_blocking_portal('asyncio') as portal:
        adapter = AsgiIpcAdapter(app, portal, channel_factory=_fake_channel_factory)
        handler = adapter.invoke_handler()

        early = make_invoke('GET', '/ping')
        handler(early)
        assert json.loads(early.rejected[0])['code'] == 'app_not_ready'

        with adapter.lifespan():
            assert events == ['startup']
            invoke = make_invoke('GET', '/ping')
            handler(invoke)
            _wait_for(lambda: invoke.resolver.resolved)
            value = invoke.resolver.resolved[0]
            assert isinstance(value, bytes)
            head, body = decode_envelope(value)
            assert head.status == 200
            assert json.loads(body) == {'pong': True}
        assert events == ['startup', 'shutdown']

        late = make_invoke('GET', '/ping')
        handler(late)
        assert json.loads(late.rejected[0])['code'] == 'app_not_ready'


def test_fallback_dispatch() -> None:
    events: list[str] = []
    app = _build_app(events)
    with start_blocking_portal('asyncio') as portal:
        adapter = AsgiIpcAdapter(app, portal, channel_factory=_fake_channel_factory)
        fallback_calls: list[Any] = []
        handler = adapter.invoke_handler(fallback=fallback_calls.append)

        other = FakeInvoke('some_pytauri_command', FakeResolver({'body': b'', 'headers': []}))
        handler(other)
        assert fallback_calls == [other]
        assert other.rejected == []


def test_unknown_command_without_fallback_rejected() -> None:
    events: list[str] = []
    app = _build_app(events)
    with start_blocking_portal('asyncio') as portal:
        adapter = AsgiIpcAdapter(app, portal, channel_factory=_fake_channel_factory)
        handler = adapter.invoke_handler()
        other = FakeInvoke('some_pytauri_command', FakeResolver({'body': b'', 'headers': []}))
        handler(other)
        assert json.loads(other.rejected[0])['code'] == 'unknown_command'


def test_lifespan_exit_cancels_open_ended_stream() -> None:
    """开放式流(SSE 推送)的 bridge task 永不自行结束;shutdown 必须取消 in-flight 请求,
    否则 `start_blocking_portal` 正常退出会永远等待该 task(真机上表现为关窗后进程挂死)。"""
    generator_cancelled = threading.Event()
    app = FastAPI()

    @app.get('/endless')
    async def endless() -> StreamingResponse:
        async def gen() -> AsyncGenerator[bytes, None]:
            try:
                while True:
                    yield b'data: ping\n\n'
                    await anyio.sleep(3600)
            finally:
                generator_cancelled.set()

        return StreamingResponse(gen(), media_type='text/event-stream')

    with start_blocking_portal('asyncio') as portal:
        adapter = AsgiIpcAdapter(app, portal, channel_factory=_fake_channel_factory)
        handler = adapter.invoke_handler()
        with adapter.lifespan():
            invoke = make_invoke('GET', '/endless')
            handler(invoke)
            _wait_for(lambda: invoke.resolver.resolved)  # 流式头已 resolve,流保持打开
        # lifespan 退出即取消;portal 正常退出不再挂死(本测试能跑完即是断言)
    assert generator_cancelled.is_set()


def test_admit_race_self_cancels_inflight_request() -> None:
    """TOCTOU 窗口:handler 过了 _admit 前闸后 shutdown 才置 False → 扫尾快照不含本
    future,开放式流永不结束 → portal 退出挂死。入册后复查必须自我取消兜住。"""
    generator_cancelled = threading.Event()
    app = FastAPI()

    @app.get('/endless')
    async def endless() -> StreamingResponse:
        async def gen() -> AsyncGenerator[bytes, None]:
            try:
                while True:
                    yield b'data: ping\n\n'
                    await anyio.sleep(3600)
            finally:
                generator_cancelled.set()

        return StreamingResponse(gen(), media_type='text/event-stream')

    class _RacingAdmitAdapter(AsgiIpcAdapter):
        """脚本化 _admit:前闸放行、入册后复查见 shutdown(复刻竞态时序)。"""

        script: list[bool] = [True, False]

        def _admit(self) -> bool:
            if self.script:
                return self.script.pop(0)
            return self._ready

    with start_blocking_portal('asyncio') as portal:
        adapter = _RacingAdmitAdapter(app, portal, channel_factory=_fake_channel_factory)
        handler = adapter.invoke_handler()
        with adapter.lifespan():
            invoke = make_invoke('GET', '/endless')
            handler(invoke)
            # 复查见 False → future.cancel();扫尾轮不依赖它,pending 自行清空
            _wait_for(lambda: not adapter._pending)  # pyright: ignore[reportPrivateUsage]
        # portal 正常退出不挂死(本测试能跑完即是断言)
    assert generator_cancelled.is_set() or not adapter._pending  # pyright: ignore[reportPrivateUsage]


def test_startup_failure_propagates_and_cleans_up() -> None:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        raise RuntimeError("db unreachable")
        yield

    app = FastAPI(lifespan=lifespan)
    with start_blocking_portal('asyncio') as portal:
        adapter = AsgiIpcAdapter(app, portal, channel_factory=_fake_channel_factory)
        with pytest.raises(LifespanError):
            with adapter.lifespan():
                raise AssertionError("lifespan body must not run")
