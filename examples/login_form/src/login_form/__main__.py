"""python -m login_form:启动 pytauri 桌面应用 或 dev HTTP server。"""

import os
import sys

from anyio.from_thread import start_blocking_portal

from login_form.app import app
from login_form.handlers import bench_echo
from pyshade.asgi import AsgiIpcAdapter
from pyshade.events import EventRegistry
from pyshade.runtime import build_fastapi_app

DEV_MODE = os.environ.get('PYSHADE_DEV') == '1'
DEV_HTTP = os.environ.get('PYSHADE_DEV_HTTP') == '1' or DEV_MODE


def main() -> int:
    registry = EventRegistry.from_app(app, extra_handlers={'bench_echo': bench_echo})
    fastapi_app = build_fastapi_app(registry, title=app.title)

    with start_blocking_portal('asyncio') as portal:
        adapter = AsgiIpcAdapter(fastapi_app, portal)

        if DEV_HTTP:
            from pyshade.asgi._dev import DevHttpServer

            dev_server = DevHttpServer(fastapi_app, portal)

        with adapter.lifespan():
            if DEV_HTTP:
                dev_server.start()

            if DEV_MODE:
                from pathlib import Path

                from pytauri_wheel.lib import builder_factory, context_factory

                src_dir = Path(__file__).parent.absolute()
                tauri_config = {'build': {'frontendDist': 'http://localhost:5173'}}
                tauri_app = builder_factory().build(
                    context=context_factory(src_dir, tauri_config=tauri_config),
                    invoke_handler=adapter.invoke_handler(),
                )
                exit_code = tauri_app.run_return()
            else:
                import signal

                print("PyShade dev HTTP server running at http://127.0.0.1:8765")
                print("Ctrl+C to stop")
                try:
                    signal.pause()
                except AttributeError:
                    input()
                exit_code = 0

            if DEV_HTTP:
                dev_server.stop()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
