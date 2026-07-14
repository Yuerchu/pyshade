"""pytauri 接线门面:AsgiIpcAdapter(design.md §3.7)。

pyshade.asgi 中唯一接触真 pytauri 的模块,且 pytauri import 全部惰性——
channel_factory 可注入,测试路径完全不需要 pytauri。
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from anyio.from_thread import BlockingPortal
from loguru import logger as l

from pyshade.asgi._bridge import RequestBridge
from pyshade.asgi._lifespan import LifespanManager
from pyshade.asgi._types import ASGIApp, ChannelFactory, ChannelLike, InvokeHandler, InvokeLike
from pyshade.asgi._wire import ASGI_COMMAND, encode_reject

_BIND_PARAMETERS: Any = {'body': None, 'headers': None, 'webview_window': None}
"""pytauri ParametersType:bind_to 只使用键,值被忽略(pytauri 文档语义)。"""


def _pytauri_channel_factory(channel_id: str, webview_window: Any) -> ChannelLike:
    """把前端 Channel id 绑定到 webview,返回真 pytauri Channel。"""
    from pytauri.ipc import JavaScriptChannelId

    js_channel_id = JavaScriptChannelId.from_str(channel_id)
    return js_channel_id.channel_on(webview_window.as_ref_webview())


class AsgiIpcAdapter:
    """把一个 ASGI app 挂到 pytauri invoke 管线;pyshade 框架内部消费,不面向最终用户。"""

    def __init__(
        self,
        app: ASGIApp,
        portal: BlockingPortal,
        *,
        channel_factory: ChannelFactory | None = None,
    ) -> None:
        self._portal = portal
        self._manager = LifespanManager(app)
        self._ready = False
        self._bridge = RequestBridge(
            app,
            channel_factory=channel_factory if channel_factory is not None else _pytauri_channel_factory,
            lifespan_state=lambda: self._manager.state,
            bind_parameters=_BIND_PARAMETERS,
        )

    def invoke_handler(self, fallback: InvokeHandler | None = None) -> InvokeHandler:
        """生成传给 `BuilderArgs.invoke_handler` 的回调;不抛异常、不阻塞(pytauri 硬约束)。

        fallback:非 ASGI 哨兵命令交给它(例如 pytauri `Commands.generate_handler`
        的产物),与 pytauri 生态共存。
        """

        def handler(invoke: InvokeLike) -> None:
            try:
                if invoke.command == ASGI_COMMAND:
                    if not self._ready:
                        invoke.reject(encode_reject('app_not_ready', "application startup has not completed"))
                        return
                    self._portal.start_task_soon(self._bridge.handle_invoke, invoke)
                elif fallback is not None:
                    fallback(invoke)
                else:
                    invoke.reject(encode_reject('unknown_command', f"unknown pyfunc command: {invoke.command}"))
            except Exception:
                l.exception("pyshade.asgi: invoke_handler dispatch error")

        return handler

    @contextmanager
    def lifespan(self) -> Generator[None, None, None]:
        """驱动 app lifespan:进入时 startup(失败抛出),退出时 shutdown。

        必须嵌在 portal 上下文内、包住 Tauri 的 `app.run_return()`。
        """
        run_future = self._portal.start_task_soon(self._manager.run)
        try:
            self._portal.call(self._manager.wait_startup)
            self._ready = True
            yield
        finally:
            self._ready = False
            self._portal.call(self._manager.request_shutdown)
            run_future.result()
