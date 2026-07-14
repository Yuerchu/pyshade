from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Request

from pyshade.asgi._bridge import RequestBridge
from pyshade.asgi._lifespan import LifespanError, LifespanManager
from pyshade.asgi._types import ChannelLike
from pyshade.asgi._wire import decode_envelope
from tests.asgi.fakes import FakeChannel, make_invoke

pytestmark = pytest.mark.anyio


def _build_app(events: list[str]) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[dict[str, Any], None]:
        events.append('startup')
        yield {'marker': 'from-lifespan'}
        events.append('shutdown')

    app = FastAPI(lifespan=lifespan)

    @app.get('/state')
    async def read_state(request: Request) -> dict[str, str]:
        return {'value': request.state.marker}

    return app


async def test_startup_state_shutdown_order() -> None:
    events: list[str] = []
    manager = LifespanManager(_build_app(events))
    async with anyio.create_task_group() as tg:
        tg.start_soon(manager.run)
        await manager.wait_startup()
        assert events == ['startup']
        state = manager.state
        assert state is not None
        assert state['marker'] == 'from-lifespan'
        await manager.request_shutdown()
        assert events == ['startup', 'shutdown']


async def test_startup_failure_raises() -> None:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        raise RuntimeError("db unreachable")
        yield

    app = FastAPI(lifespan=lifespan)
    manager = LifespanManager(app)
    async with anyio.create_task_group() as tg:
        tg.start_soon(manager.run)
        with pytest.raises(LifespanError):
            await manager.wait_startup()


async def test_app_without_lifespan_degrades() -> None:
    async def http_only_app(scope: Any, receive: Any, send: Any) -> None:
        raise RuntimeError("lifespan not supported")

    manager = LifespanManager(http_only_app)
    async with anyio.create_task_group() as tg:
        tg.start_soon(manager.run)
        await manager.wait_startup()  # 不抛:降级
        assert manager.state is None
        await manager.request_shutdown()  # no-op


async def test_state_flows_into_requests() -> None:
    events: list[str] = []
    app = _build_app(events)
    manager = LifespanManager(app)
    async with anyio.create_task_group() as tg:
        tg.start_soon(manager.run)
        await manager.wait_startup()

        def factory(channel_id: str, webview_window: Any) -> ChannelLike:
            return FakeChannel()

        bridge = RequestBridge(app, channel_factory=factory, lifespan_state=lambda: manager.state, bind_parameters={})
        invoke = make_invoke('GET', '/state')
        await bridge.handle_invoke(invoke)
        value = invoke.resolver.resolved[0]
        assert isinstance(value, bytes)
        head, body = decode_envelope(value)
        assert head.status == 200
        assert b'from-lifespan' in body

        await manager.request_shutdown()
