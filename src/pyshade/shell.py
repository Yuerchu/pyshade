"""运行时壳层入口:standalone(打包产物)与 venv 开发(pytauri-wheel)双形态统一。

形态检测用 pytauri 官方内部标志 `sys._pytauri_standalone`(其 standalone 协议的一部分,
随锁定的 minor 版本一起审):
- standalone:factories 来自 `pytauri`(ext_mod 由 Rust 二进制内存注入),
  `context_factory()` 无参——frontendDist 已在 `pyshade package` 时烤入二进制;
- 开发:factories 来自 `pytauri_wheel.lib`;PYSHADE_DEV=1 → vite dev server + DevHttpServer,
  否则 dist_dir(env PYSHADE_DIST 覆盖)转相对路径(Windows 绝对路径会被 Tauri 的
  FrontendDist 误判为 URL,M1 实测教训)。

pytauri/pytauri_wheel 全部惰性 import:裸 pyshade 环境(无 ext_mod 提供者)import pytauri 即崩。
`PYSHADE_SMOKE=1` → RunEvent.Ready 时 exit(0),CI 冒烟用。
"""

import os
import sys
from multiprocessing import freeze_support
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyshade.asgi._dev import DevHttpServer

from anyio.from_thread import start_blocking_portal

from pyshade.app import ShadeApp
from pyshade.asgi import AsgiIpcAdapter
from pyshade.components.base import Handler
from pyshade.events import EventRegistry
from pyshade.runtime import build_fastapi_app


def _resolve_dist(dist_dir: Path | None, config_dir: Path) -> Path:
    override = os.environ.get('PYSHADE_DIST')
    resolved = Path(override) if override else dist_dir
    if resolved is None:
        raise SystemExit(
            "缺少前端产物目录:请传 dist_dir= 或设置 PYSHADE_DIST;产物由 `pyshade bundle <模块:属性>` 或 vite build 生成"
        )
    if not (resolved / 'index.html').exists():
        raise SystemExit(f"前端产物不存在:{resolved};先运行 pyshade bundle 或 pnpm -C frontend build")
    return resolved


def _smoke_callback() -> Any:
    from pytauri import RunEvent

    def on_event(app_handle: Any, event: Any) -> None:
        if isinstance(event, RunEvent.Ready):
            app_handle.exit(0)

    return on_event


def run(
    app: ShadeApp,
    *,
    config_dir: Path,
    dist_dir: Path | None = None,
    extra_handlers: dict[str, Handler] | None = None,
) -> int:
    """启动 pytauri 桌面应用;返回退出码。config_dir = Tauri.toml + capabilities 所在目录。"""
    freeze_support()  # standalone 必需:multiprocessing spawn 不加会无限拉起自身

    registry = EventRegistry.from_app(app, extra_handlers=extra_handlers)
    fastapi_app = build_fastapi_app(registry, title=app.title)

    standalone = bool(getattr(sys, '_pytauri_standalone', False))
    dev_mode = os.environ.get('PYSHADE_DEV') == '1' and not standalone

    if standalone:
        from pytauri import builder_factory, context_factory

        def make_context() -> Any:
            return context_factory()
    else:
        if dev_mode:
            tauri_config: dict[str, Any] = {'build': {'frontendDist': 'http://localhost:5173'}}
        else:
            dist = _resolve_dist(dist_dir, config_dir)
            rel_dist = Path(os.path.relpath(dist.absolute(), config_dir.absolute())).as_posix()
            tauri_config = {'build': {'frontendDist': rel_dist}}

        from pytauri_wheel.lib import builder_factory, context_factory

        def make_context() -> Any:
            return context_factory(config_dir.absolute(), tauri_config=tauri_config)

    with start_blocking_portal('asyncio') as portal:
        adapter = AsgiIpcAdapter(fastapi_app, portal)

        dev_server: DevHttpServer | None = None
        if dev_mode:
            from pyshade.asgi._dev import DevHttpServer as _DevHttpServer

            dev_server = _DevHttpServer(fastapi_app, portal)

        with adapter.lifespan():
            if dev_server is not None:
                dev_server.start()
            tauri_app = builder_factory().build(
                context=make_context(),
                invoke_handler=adapter.invoke_handler(),
            )
            if os.environ.get('PYSHADE_SMOKE') == '1':
                exit_code = tauri_app.run_return(_smoke_callback())
            else:
                exit_code = tauri_app.run_return()
            if dev_server is not None:
                dev_server.stop()

    return exit_code
