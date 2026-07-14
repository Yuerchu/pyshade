import json
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from anyio.from_thread import start_blocking_portal
from fastapi import FastAPI

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
