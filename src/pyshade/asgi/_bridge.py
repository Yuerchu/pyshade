"""请求管线核心:Invoke → ASGI scope → app → resolve/Channel(design.md §3.7)。

只依赖 `_types` 的 Protocol,运行时零 pytauri import;真实接线在 `_adapter`。
`handle_invoke` 对外保证永不抛异常(pytauri invoke_handler 硬约束)。
"""

from collections.abc import Callable
from dataclasses import replace
from typing import Any
from urllib.parse import unquote

import anyio
from loguru import logger as l

from pyshade.asgi._types import (
    ASGIApp,
    ChannelLike,
    InvokeLike,
    Message,
    Receive,
    ResolverLike,
    Scope,
)
from pyshade.asgi._wire import (
    RequestMeta,
    ResponseHead,
    WireError,
    encode_body_frame,
    encode_end_frame,
    encode_envelope,
    encode_error_frame,
    encode_reject,
    parse_request_meta,
    strip_wire_headers,
)

_SYNTHETIC_500_HEAD = ResponseHead(status=500, headers=[(b'content-type', b'text/plain; charset=utf-8')])
_SYNTHETIC_500_BODY = b'Internal Server Error'


def build_http_scope(
    meta: RequestMeta,
    headers: list[tuple[bytes, bytes]],
    *,
    state: dict[str, Any] | None = None,
    extensions: dict[str, Any] | None = None,
) -> Scope:
    """按 ASGI HTTP scope 规范构造 scope;剥掉 x-pyshade-* 传输层 headers。

    scheme 固定 "http":自定义 scheme 会破坏 Starlette 的 URL 构造与重定向,
    进程内 IPC 事实上比 https 更安全,此处是兼容性取舍。
    """
    try:
        path = unquote(meta.raw_path.decode('ascii'))
    except UnicodeDecodeError as exc:
        # 与 parse_request_meta 同属 meta 层防线:裸 UnicodeDecodeError 会让 invoke 永不 settle
        raise WireError('bad_request_meta', "x-pyshade-path header is not valid ASCII") from exc
    scope: Scope = {
        'type': 'http',
        'asgi': {'version': '3.0', 'spec_version': '2.3'},
        'http_version': '1.1',
        'method': meta.method,
        'scheme': 'http',
        'path': path,
        'raw_path': meta.raw_path,
        'query_string': meta.query_string,
        'root_path': '',
        'headers': strip_wire_headers(headers),
        'client': ('ipc', 0),
        'server': ('pyshade', None),
    }
    if state is not None:
        scope['state'] = dict(state)
    if extensions is not None:
        scope['extensions'] = extensions
    return scope


def _make_receive(body: bytes, disconnected: anyio.Event) -> Receive:
    """M0 请求体不分块:首次返回全量 body,之后挂起直至响应完成 → http.disconnect。"""
    delivered = False

    async def receive() -> Message:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {'type': 'http.request', 'body': body, 'more_body': False}
        await disconnected.wait()
        return {'type': 'http.disconnect'}

    return receive


class _ResponseSink:
    """ASGI send 侧状态机:首个 body 事件 more_body=True → 流式,否则单帧。"""

    def __init__(self, resolver: ResolverLike, channel_factory: Callable[[], ChannelLike]) -> None:
        self._resolver = resolver
        self._make_channel = channel_factory
        self._head: ResponseHead | None = None
        self._channel: ChannelLike | None = None
        self.wire_started = False
        self.streaming = False
        self.done = False
        self.disconnected = anyio.Event()

    async def send(self, message: Message) -> None:
        msg_type = message['type']
        if msg_type == 'http.response.start':
            if self._head is not None:
                raise RuntimeError("duplicate http.response.start message")
            raw_headers: list[tuple[Any, Any]] = list(message.get('headers') or [])
            self._head = ResponseHead(
                status=int(message['status']),
                headers=[(bytes(k), bytes(v)) for k, v in raw_headers],
            )
        elif msg_type == 'http.response.body':
            if self._head is None:
                raise RuntimeError("http.response.body sent before http.response.start")
            if self.done:
                return
            body = bytes(message.get('body') or b'')
            more = bool(message.get('more_body', False))
            if not self.wire_started:
                if more:
                    # 切流式:先建 channel(失败则尚未 resolve,可走 reject),再发流式头
                    self.streaming = True
                    self._channel = self._make_channel()
                    self._resolver.resolve(encode_envelope(replace(self._head, stream=True), b''))
                    self.wire_started = True
                    if body:
                        self._channel.send(encode_body_frame(body))
                else:
                    self._resolver.resolve(encode_envelope(self._head, body))
                    self.wire_started = True
                    self.done = True
                    self.disconnected.set()
            else:
                channel = self._channel
                if channel is None:
                    raise RuntimeError("streaming body without channel")
                if body:
                    channel.send(encode_body_frame(body))
                if not more:
                    channel.send(encode_end_frame())
                    self.done = True
                    self.disconnected.set()
        # 其余消息类型(trailers 等)M0 忽略

    def abort(self, code: str, message: str) -> None:
        """流式中止:发 ERROR 帧并终结。"""
        if self._channel is not None and not self.done:
            try:
                self._channel.send(encode_error_frame(code, message))
            except Exception:
                # 窗口已毁时 channel.send 自身会抛:abort 常在异常路径被调,二次抛错会在
                # handle_invoke 兜底日志里叠出误导性的双 traceback——降级为单条 warning
                l.warning("pyshade.asgi: ERROR 帧投递失败(channel 已销毁),中止流: {}", code)
        self.done = True
        self.disconnected.set()

    def finish(self) -> None:
        self.disconnected.set()


class RequestBridge:
    """每个 adapter 一个实例;handle_invoke 每请求一个 portal task。"""

    def __init__(
        self,
        app: ASGIApp,
        *,
        channel_factory: Callable[[str, Any], ChannelLike],
        lifespan_state: Callable[[], dict[str, Any] | None],
        bind_parameters: Any,
    ) -> None:
        self._app = app
        self._channel_factory = channel_factory
        self._lifespan_state = lifespan_state
        self._bind_parameters = bind_parameters

    async def handle_invoke(self, invoke: InvokeLike) -> None:
        try:
            await self._handle(invoke)
        except Exception:
            l.exception("pyshade.asgi: unhandled error in request pipeline")

    async def _handle(self, invoke: InvokeLike) -> None:
        resolver = invoke.bind_to(self._bind_parameters)
        if resolver is None:
            return  # bind_to 失败时 pytauri 已自动 reject
        args = resolver.arguments
        body: bytes = args['body']
        headers: list[tuple[bytes, bytes]] = args['headers']
        webview_window: Any = args.get('webview_window')

        try:
            meta = parse_request_meta(headers)
        except WireError as exc:
            resolver.reject(encode_reject(exc.code, exc.message))
            return

        def channel_factory() -> ChannelLike:
            if meta.channel_id is None:
                raise WireError('bad_request_meta', "streaming response requires x-pyshade-channel header")
            return self._channel_factory(meta.channel_id, webview_window)

        sink = _ResponseSink(resolver, channel_factory)
        extensions: dict[str, Any] = {}
        if webview_window is not None:
            extensions['pyshade.ipc'] = {'webview_window': webview_window}
        try:
            scope = build_http_scope(meta, headers, state=self._lifespan_state(), extensions=extensions)
        except WireError as exc:
            resolver.reject(encode_reject(exc.code, exc.message))
            return
        receive = _make_receive(body, sink.disconnected)

        try:
            await self._app(scope, receive, sink.send)
        except WireError as exc:
            if not sink.wire_started:
                resolver.reject(encode_reject(exc.code, exc.message))
            else:
                l.error("pyshade.asgi: wire error after response started: {}", exc.message)
                sink.abort(exc.code, exc.message)
        except Exception:
            l.exception("pyshade.asgi: ASGI application error")
            if not sink.wire_started:
                resolver.resolve(encode_envelope(_SYNTHETIC_500_HEAD, _SYNTHETIC_500_BODY))
            elif sink.streaming and not sink.done:
                sink.abort('app_error', "application error during streaming response")
        else:
            if not sink.wire_started:
                l.error("pyshade.asgi: ASGI app returned without completing the response")
                resolver.resolve(encode_envelope(_SYNTHETIC_500_HEAD, _SYNTHETIC_500_BODY))
            elif sink.streaming and not sink.done:
                sink.abort('incomplete_response', "ASGI app returned before ending the stream")
        finally:
            sink.finish()
