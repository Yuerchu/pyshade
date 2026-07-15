"""python -m component_gallery:启动 pytauri 桌面应用。

两态:
- 默认(生产):frontendDist = <repo>/frontend/dist(vite build 产物)
- PYSHADE_DEV=1:frontendDist = vite dev server(http://localhost:5173)+ dev HTTP server
"""

import os
import sys
from pathlib import Path
from typing import Any

from anyio.from_thread import start_blocking_portal

from component_gallery.runtime import build_runtime
from pyshade.asgi import AsgiIpcAdapter

DEV_MODE = os.environ.get('PYSHADE_DEV') == '1'

SRC_TAURI_DIR = Path(__file__).parent.absolute()
REPO_ROOT = SRC_TAURI_DIR.parent.parent.parent.parent


def main() -> int:
    _registry, fastapi_app = build_runtime()

    if DEV_MODE:
        tauri_config: dict[str, Any] = {'build': {'frontendDist': 'http://localhost:5173'}}
    else:
        dist = REPO_ROOT / 'frontend' / 'dist'
        if not dist.exists():
            print(f"前端产物不存在:{dist};先运行 pnpm -C frontend build", file=sys.stderr)
            return 1
        # 必须相对路径:Windows 绝对路径会被 FrontendDist 误判为 URL(scheme 'c:')
        rel_dist = Path(os.path.relpath(dist, SRC_TAURI_DIR)).as_posix()
        tauri_config = {'build': {'frontendDist': rel_dist}}

    from pytauri_wheel.lib import builder_factory, context_factory

    with start_blocking_portal('asyncio') as portal:
        adapter = AsgiIpcAdapter(fastapi_app, portal)

        if DEV_MODE:
            from pyshade.asgi._dev import DevHttpServer

            dev_server = DevHttpServer(fastapi_app, portal)

        with adapter.lifespan():
            if DEV_MODE:
                dev_server.start()
            tauri_app = builder_factory().build(
                context=context_factory(SRC_TAURI_DIR, tauri_config=tauri_config),
                invoke_handler=adapter.invoke_handler(),
            )
            exit_code = tauri_app.run_return()
            if DEV_MODE:
                dev_server.stop()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
