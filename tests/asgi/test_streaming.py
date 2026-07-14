import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from pyshade.asgi._bridge import RequestBridge
from pyshade.asgi._types import ChannelLike
from pyshade.asgi._wire import FRAME_BODY, FRAME_END, FRAME_ERROR, decode_envelope
from tests.asgi.fakes import FakeChannel, FakeInvoke, make_invoke

pytestmark = pytest.mark.anyio


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get('/stream')
    async def stream() -> StreamingResponse:
        async def gen() -> AsyncIterator[bytes]:
            yield b'one'
            yield b'two'
            yield b'three'

        return StreamingResponse(gen(), media_type='text/plain')

    @app.get('/stream-error')
    async def stream_error() -> StreamingResponse:
        async def bad() -> AsyncIterator[bytes]:
            yield b'first'
            raise RuntimeError("stream kaboom")

        return StreamingResponse(bad(), media_type='text/plain')

    return app


def make_bridge(app: Any) -> tuple[RequestBridge, list[FakeChannel]]:
    channels: list[FakeChannel] = []

    def factory(channel_id: str, webview_window: Any) -> ChannelLike:
        channel = FakeChannel()
        channels.append(channel)
        return channel

    bridge = RequestBridge(app, channel_factory=factory, lifespan_state=lambda: None, bind_parameters={})
    return bridge, channels


def stream_head(invoke: FakeInvoke) -> tuple[int, bool]:
    assert len(invoke.resolver.resolved) == 1
    value = invoke.resolver.resolved[0]
    assert isinstance(value, bytes)
    head, body = decode_envelope(value)
    assert body == b''
    return head.status, head.stream


async def test_streaming_frames_in_order() -> None:
    bridge, channels = make_bridge(_build_app())
    invoke = make_invoke('GET', '/stream')
    await bridge.handle_invoke(invoke)

    status, stream = stream_head(invoke)
    assert status == 200
    assert stream is True

    assert len(channels) == 1
    frames = channels[0].sent
    assert frames == [
        bytes((FRAME_BODY,)) + b'one',
        bytes((FRAME_BODY,)) + b'two',
        bytes((FRAME_BODY,)) + b'three',
        bytes((FRAME_END,)),
    ]


async def test_stream_error_emits_error_frame() -> None:
    bridge, channels = make_bridge(_build_app())
    invoke = make_invoke('GET', '/stream-error')
    await bridge.handle_invoke(invoke)

    status, stream = stream_head(invoke)
    assert status == 200
    assert stream is True

    frames = channels[0].sent
    assert frames[0] == bytes((FRAME_BODY,)) + b'first'
    last = frames[-1]
    assert isinstance(last, bytes)
    assert last[0] == FRAME_ERROR
    payload = json.loads(last[1:])
    assert payload['code'] == 'app_error'
    assert 'kaboom' not in payload['message']  # 异常细节不泄露给前端


async def test_stream_without_channel_is_rejected() -> None:
    bridge, channels = make_bridge(_build_app())
    invoke = make_invoke('GET', '/stream', channel=None)
    await bridge.handle_invoke(invoke)

    assert invoke.resolver.resolved == []
    assert len(invoke.resolver.rejected) == 1
    payload = json.loads(invoke.resolver.rejected[0])
    assert payload['code'] == 'bad_request_meta'
    assert channels == []
