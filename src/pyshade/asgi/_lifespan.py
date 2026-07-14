"""ASGI lifespan 协议驱动器(design.md §3.7)。

lifespan 主循环(run)作为后台任务与 Tauri 主循环并行跑在 portal loop 里:
startup 失败向上抛(窗口根本不创建);app 不支持 lifespan 时降级为警告。
"""

import math
from typing import Any

import anyio
from loguru import logger as l

from pyshade.asgi._types import ASGIApp, Message, Scope


class LifespanError(RuntimeError):
    """ASGI lifespan startup 失败。"""


class LifespanManager:
    """驱动一个 ASGI app 的 lifespan 协议。

    用法:先在事件循环里把 `run()` 作为后台任务启动,再 await `wait_startup()`;
    退出时 await `request_shutdown()`。三者必须在同一事件循环内。
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self._state: dict[str, Any] = {}
        self._supported = True
        self._startup_done = anyio.Event()
        self._shutdown_done = anyio.Event()
        self._startup_error: str | None = None
        self._shutdown_error: str | None = None
        send, receive = anyio.create_memory_object_stream[Message](math.inf)
        self._to_app = send
        self._from_manager = receive

    @property
    def state(self) -> dict[str, Any] | None:
        """lifespan scope 携带的 state;app 不支持 lifespan 时为 None。"""
        if not self._supported:
            return None
        return self._state

    async def run(self) -> None:
        """lifespan 主协程,运行至 shutdown 完成或 app 退出。"""
        scope: Scope = {
            'type': 'lifespan',
            'asgi': {'version': '3.0', 'spec_version': '2.0'},
            'state': self._state,
        }
        try:
            await self._app(scope, self._from_manager.receive, self._send)
        except Exception as exc:
            if not self._startup_done.is_set():
                # startup 完成前抛异常:按 ASGI spec 视为不支持 lifespan,降级继续
                self._supported = False
                l.warning("ASGI app does not support lifespan, continuing without it: {}", exc)
                self._startup_done.set()
            else:
                # startup.failed 后 Starlette 会 re-raise,错误已经由 failed 消息传达过
                if self._startup_error is None and not self._shutdown_done.is_set():
                    self._shutdown_error = str(exc)
                    l.exception("pyshade.asgi: lifespan task crashed")
                self._shutdown_done.set()
        else:
            self._startup_done.set()
            self._shutdown_done.set()

    async def _send(self, message: Message) -> None:
        msg_type = message['type']
        if msg_type == 'lifespan.startup.complete':
            self._startup_done.set()
        elif msg_type == 'lifespan.startup.failed':
            self._startup_error = str(message.get('message', ''))
            self._startup_done.set()
        elif msg_type == 'lifespan.shutdown.complete':
            self._shutdown_done.set()
        elif msg_type == 'lifespan.shutdown.failed':
            self._shutdown_error = str(message.get('message', ''))
            self._shutdown_done.set()

    async def wait_startup(self) -> None:
        """发送 startup 事件并等待完成;失败抛 LifespanError。"""
        await self._to_app.send({'type': 'lifespan.startup'})
        await self._startup_done.wait()
        if self._startup_error is not None:
            raise LifespanError(f"ASGI lifespan startup failed: {self._startup_error}")

    async def request_shutdown(self) -> None:
        """发送 shutdown 事件并等待完成;shutdown 失败只记日志。"""
        if not self._supported:
            return
        try:
            await self._to_app.send({'type': 'lifespan.shutdown'})
        except anyio.BrokenResourceError:
            return
        await self._shutdown_done.wait()
        if self._shutdown_error is not None:
            l.error("pyshade.asgi: lifespan shutdown failed: {}", self._shutdown_error)
