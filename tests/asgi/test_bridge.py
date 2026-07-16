import json
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from pyshade.asgi._bridge import RequestBridge
from pyshade.asgi._types import ChannelLike
from pyshade.asgi._wire import H_METHOD, H_PATH, ResponseHead, decode_envelope
from tests.asgi.fakes import FakeChannel, FakeInvoke, FakeResolver, make_invoke

pytestmark = pytest.mark.anyio


class Item(BaseModel):
    name: str


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get('/hello')
    async def hello() -> dict[str, str]:
        return {'msg': 'hi'}

    @app.post('/echo')
    async def echo(request: Request) -> Response:
        return Response(content=await request.body(), media_type='application/octet-stream')

    @app.post('/items')
    async def create_item(item: Item) -> dict[str, str]:
        return {'name': item.name}

    @app.get('/boom')
    async def boom() -> None:
        raise RuntimeError("kaboom")

    @app.get('/state')
    async def read_state(request: Request) -> dict[str, str]:
        return {'value': request.state.marker}

    return app


def make_bridge(app: Any, lifespan_state: dict[str, Any] | None = None) -> tuple[RequestBridge, list[FakeChannel]]:
    channels: list[FakeChannel] = []

    def factory(channel_id: str, webview_window: Any) -> ChannelLike:
        channel = FakeChannel()
        channels.append(channel)
        return channel

    bridge = RequestBridge(
        app,
        channel_factory=factory,
        lifespan_state=lambda: lifespan_state,
        bind_parameters={'marker': True},
    )
    return bridge, channels


def resolved_envelope(invoke: FakeInvoke) -> tuple[ResponseHead, bytes]:
    assert not invoke.resolver.rejected
    assert len(invoke.resolver.resolved) == 1
    value = invoke.resolver.resolved[0]
    assert isinstance(value, bytes)
    return decode_envelope(value)


async def test_single_frame_ok() -> None:
    bridge, channels = make_bridge(_build_app())
    invoke = make_invoke('GET', '/hello')
    await bridge.handle_invoke(invoke)
    head, body = resolved_envelope(invoke)
    assert head.status == 200
    assert head.stream is False
    assert json.loads(body) == {'msg': 'hi'}
    assert channels == []  # 单帧路径不创建 channel


async def test_echo_request_body() -> None:
    bridge, _ = make_bridge(_build_app())
    invoke = make_invoke('POST', '/echo', body=b'\x00\x01binary')
    await bridge.handle_invoke(invoke)
    head, body = resolved_envelope(invoke)
    assert head.status == 200
    assert body == b'\x00\x01binary'


async def test_not_found() -> None:
    bridge, _ = make_bridge(_build_app())
    invoke = make_invoke('GET', '/nope')
    await bridge.handle_invoke(invoke)
    head, _ = resolved_envelope(invoke)
    assert head.status == 404


async def test_validation_error_422() -> None:
    bridge, _ = make_bridge(_build_app())
    invoke = make_invoke('POST', '/items', body=b'{}', extra_headers=[(b'content-type', b'application/json')])
    await bridge.handle_invoke(invoke)
    head, _ = resolved_envelope(invoke)
    assert head.status == 422


async def test_route_exception_becomes_500_envelope() -> None:
    bridge, _ = make_bridge(_build_app())
    invoke = make_invoke('GET', '/boom')
    await bridge.handle_invoke(invoke)
    head, _ = resolved_envelope(invoke)
    assert head.status == 500


async def test_naked_app_exception_synthesizes_500() -> None:
    async def naked_app(scope: Any, receive: Any, send: Any) -> None:
        raise RuntimeError("no middleware here")

    bridge, _ = make_bridge(naked_app)
    invoke = make_invoke('GET', '/x')
    await bridge.handle_invoke(invoke)
    head, body = resolved_envelope(invoke)
    assert head.status == 500
    assert body == b'Internal Server Error'
    assert b'no middleware here' not in body  # traceback 不泄露给前端


async def test_app_returning_without_response_synthesizes_500() -> None:
    async def silent_app(scope: Any, receive: Any, send: Any) -> None:
        return

    bridge, _ = make_bridge(silent_app)
    invoke = make_invoke('GET', '/x')
    await bridge.handle_invoke(invoke)
    head, body = resolved_envelope(invoke)
    assert head.status == 500
    assert body == b'Internal Server Error'


async def test_missing_meta_header_rejected() -> None:
    bridge, _ = make_bridge(_build_app())
    resolver = FakeResolver({'body': b'', 'headers': [(H_PATH, b'/')], 'webview_window': None})
    invoke = FakeInvoke('__pyshade_asgi__', resolver)
    await bridge.handle_invoke(invoke)
    assert resolver.resolved == []
    assert len(resolver.rejected) == 1
    payload = json.loads(resolver.rejected[0])
    assert payload['code'] == 'bad_request_meta'


async def test_non_ascii_path_header_rejected_not_hung() -> None:
    # meta 层解码防线:裸 UnicodeDecodeError 会逃出 except WireError,invoke 永不 settle
    bridge, _ = make_bridge(_build_app())
    resolver = FakeResolver(
        {'body': b'', 'headers': [(H_METHOD, b'GET'), (H_PATH, b'/caf\xc3\xa9')], 'webview_window': None}
    )
    invoke = FakeInvoke('__pyshade_asgi__', resolver)
    await bridge.handle_invoke(invoke)
    assert resolver.resolved == []
    assert len(resolver.rejected) == 1
    payload = json.loads(resolver.rejected[0])
    assert payload['code'] == 'bad_request_meta'


async def test_non_ascii_method_header_rejected_not_hung() -> None:
    bridge, _ = make_bridge(_build_app())
    resolver = FakeResolver({'body': b'', 'headers': [(H_METHOD, b'G\xc9T'), (H_PATH, b'/')], 'webview_window': None})
    invoke = FakeInvoke('__pyshade_asgi__', resolver)
    await bridge.handle_invoke(invoke)
    assert resolver.resolved == []
    assert len(resolver.rejected) == 1
    payload = json.loads(resolver.rejected[0])
    assert payload['code'] == 'bad_request_meta'


async def test_bind_parameters_passthrough() -> None:
    bridge, _ = make_bridge(_build_app())
    invoke = make_invoke('GET', '/hello')
    await bridge.handle_invoke(invoke)
    assert invoke.bound_parameters == {'marker': True}


async def test_lifespan_state_injected() -> None:
    bridge, _ = make_bridge(_build_app(), lifespan_state={'marker': 'from-lifespan'})
    invoke = make_invoke('GET', '/state')
    await bridge.handle_invoke(invoke)
    head, body = resolved_envelope(invoke)
    assert head.status == 200
    assert json.loads(body) == {'value': 'from-lifespan'}


async def test_concurrent_requests_are_isolated() -> None:
    bridge, _ = make_bridge(_build_app())
    invokes = [make_invoke('POST', '/echo', body=f'payload-{i}'.encode()) for i in range(20)]
    async with anyio.create_task_group() as tg:
        for invoke in invokes:
            tg.start_soon(bridge.handle_invoke, invoke)
    for i, invoke in enumerate(invokes):
        head, body = resolved_envelope(invoke)
        assert head.status == 200
        assert body == f'payload-{i}'.encode()
