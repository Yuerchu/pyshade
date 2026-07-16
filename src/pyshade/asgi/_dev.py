"""dev 模式 HTTP server:同一 ASGI app 额外经 uvicorn 暴露在 localhost(design.md §3.7)。

uvicorn 跑在 portal 的同一个 asyncio loop 里(portal.start_task_soon),lifespan 由
AsgiIpcAdapter 统一驱动(uvicorn lifespan="off"),避免 lifespan state 跨 loop 失效。
生产路径不 import 本模块。
"""

from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from anyio.from_thread import BlockingPortal
from loguru import logger as l

from pyshade.asgi._types import ASGIApp


@dataclass(frozen=True, slots=True)
class DevServerConfig:
    host: str = '127.0.0.1'
    port: int = 8765
    log_level: str = 'warning'


class DevHttpServer:
    """开发用 HTTP server,便于浏览器调试事件路由(不经 Tauri IPC)。"""

    def __init__(
        self,
        app: ASGIApp,
        portal: BlockingPortal,
        config: DevServerConfig | None = None,
    ) -> None:
        self._app = app
        self._portal = portal
        self._config = config or DevServerConfig()
        self._server: Any = None

    def start(self) -> None:
        try:
            import uvicorn
        except ImportError as exc:
            raise RuntimeError("dev HTTP server 需要 uvicorn;请 `uv add --group dev uvicorn`") from exc

        cfg = uvicorn.Config(
            self._app,
            host=self._config.host,
            port=self._config.port,
            log_level=self._config.log_level,
            lifespan='off',
        )
        self._server = uvicorn.Server(cfg)
        self._server.config.setup_event_loop = lambda: None
        future = self._portal.start_task_soon(self._server.serve)
        port = self._config.port

        def _report(f: 'Future[None]') -> None:
            # start_task_soon 的 future 无人 await:启动失败(端口占用等)不检查就是静默失败,
            # 用户只看到上面那条误导性的 "dev HTTP server: http://..." info 日志
            if f.cancelled():
                return
            try:
                exc = f.exception()
            except BaseException as raised:  # noqa: BLE001  # SystemExit 等 BaseException 也要报出来
                exc = raised
            if exc is not None:
                l.opt(exception=exc).error("pyshade dev HTTP server 启动/运行失败(端口 {} 被占用?)", port)

        future.add_done_callback(_report)
        l.info("pyshade dev HTTP server: http://{}:{}", self._config.host, self._config.port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
