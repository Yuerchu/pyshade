"""推送通道(M1 Phase 4):PatchBus 扇出 + GET /_shade/push SSE。

单一 SSE 端点跑在既有 ASGI 栈上:IPC 模式即一条常驻流式请求(StreamingResponse
触发 asgi 层既有的 more_body 流式分支,零新协议);dev HTTP 模式由 uvicorn 原样暴露。

订阅时序:先订阅、后推全量快照——快照期间的变更进入订阅队列,无缝隙;
前端重连后重新收到快照,merge 语义天然幂等,不需要 patch 序号。
"""

import json
from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager
from typing import Any

import anyio
import anyio.lowlevel
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from loguru import logger as l
from pydantic_core import to_jsonable_python

from pyshade.state import ServerRef, server_state_snapshot, set_dirty_publisher

_SUBSCRIBER_BUFFER = 64


class PatchBus:
    """进程级 patch 扇出:请求外的 ServerState 变更广播给全部订阅者。

    慢消费者(缓冲区满)断流 + 告警——强制该订阅者重连,重连快照补齐终态,不阻塞发布方
    (丢帧不可静默:丢掉的可能恰是终态帧,而前端只在流断开时才重连)。
    发布与订阅须在同一事件循环(portal loop)上,anyio memory stream 非线程安全;
    publish 在有订阅者时校验 loop 归属,跨线程/跨 loop 写 ServerState 构造期即抛
    RuntimeError(而非静默竞态)。
    """

    def __init__(self) -> None:
        self._subscribers: list[MemoryObjectSendStream[dict[str, Any]]] = []
        self._token: object | None = None
        """首个订阅者进场时惰性绑定的事件循环 token;订阅清零后由下一个订阅者重绑。"""

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, patch: dict[str, Any]) -> None:
        # 有订阅者才校验 loop 归属:anyio memory stream 非线程安全,跨线程 send_nowait
        # 是静默竞态;无订阅者时 publish 本就是 no-op,值已落 ServerState、后续订阅经
        # 快照收敛(启动期主线程写状态是合法惯用法,不误伤)。
        if self._subscribers:
            try:
                current: object | None = anyio.lowlevel.current_token()
            except RuntimeError:  # sniffio.AsyncLibraryNotFoundError(RuntimeError 子类):纯同步线程
                current = None
            # 注意 ==:asyncio 后端每次调用返回新的 EventLoopToken 包装对象,按 loop 相等比较
            if current != self._token:
                raise RuntimeError(
                    "ServerState 在应用事件循环之外(或另一事件循环)变更,无法安全推送给已连接的订阅者:"
                    "请在事件 handler 或其 spawn 的任务内修改状态;"
                    "外部线程请用 anyio.from_thread.run_sync(...) 把赋值切回事件循环"
                )
        for send in list(self._subscribers):
            try:
                send.send_nowait(patch)
            except anyio.WouldBlock:
                # 丢帧不可静默:丢掉的可能恰是终态帧,而前端只在流断开时才重连拿快照——
                # 关闭该订阅者的发送端强制其 SSE 终结(缓冲内已入队消息仍可 drain),
                # 前端重连后先收全量快照,merge 幂等收敛;期间 UI 显示 Connection lost
                if send in self._subscribers:
                    self._subscribers.remove(send)
                send.close()
                l.warning(
                    "pyshade.push: 订阅者缓冲区满({}),关闭该订阅流强制重连;快照会补齐终态",
                    _SUBSCRIBER_BUFFER,
                )
            except (anyio.ClosedResourceError, anyio.BrokenResourceError):
                if send in self._subscribers:
                    self._subscribers.remove(send)

    @contextmanager
    def subscribe(self) -> Generator[MemoryObjectReceiveStream[dict[str, Any]], None, None]:
        if not self._subscribers:
            # (重)绑定当前事件循环:覆盖测试/dev 重启换 loop 的场景
            self._token = anyio.lowlevel.current_token()
        send, receive = anyio.create_memory_object_stream[dict[str, Any]](_SUBSCRIBER_BUFFER)
        self._subscribers.append(send)
        try:
            yield receive
        finally:
            if send in self._subscribers:
                self._subscribers.remove(send)
            send.close()
            receive.close()


def _sse_event(patches: list[dict[str, Any]]) -> bytes:
    payload = json.dumps({'patches': patches}, ensure_ascii=False)
    return f'data: {payload}\n\n'.encode()


def mount_push_route(app: FastAPI, *, bus: PatchBus | None = None) -> PatchBus:
    """挂载 GET /_shade/push 并把请求外的 ServerState 变更接到 bus。

    进程内 publisher 是全局单点:多次挂载(如测试多 app)以最后一次为准。
    """
    active_bus = bus if bus is not None else PatchBus()

    def publish_dirty(ref: 'ServerRef[Any]', value: Any) -> None:
        active_bus.publish({'target': ref.target, 'props': {ref.field: to_jsonable_python(value)}})

    set_dirty_publisher(publish_dirty)

    @app.get('/_shade/push')
    async def push_stream() -> StreamingResponse:  # pyright: ignore[reportUnusedFunction]
        async def gen() -> AsyncIterator[bytes]:
            with active_bus.subscribe() as receiver:
                yield _sse_event(server_state_snapshot())
                async for patch in receiver:
                    yield _sse_event([patch])

        return StreamingResponse(
            gen(),
            media_type='text/event-stream',
            headers={'cache-control': 'no-cache', 'x-accel-buffering': 'no'},
        )

    return active_bus
