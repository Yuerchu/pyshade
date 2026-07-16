"""DevHttpServer:启动失败(端口占用)必须报错而非静默(start_task_soon 的 future 无人 await)。"""

import socket
import time
from collections.abc import Callable

from anyio.from_thread import start_blocking_portal
from fastapi import FastAPI
from loguru import logger as l

from pyshade.asgi._dev import DevHttpServer, DevServerConfig


def _wait_for(predicate: Callable[[], object], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met within timeout")


def test_port_in_use_is_reported() -> None:
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(('127.0.0.1', 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]

    errors: list[str] = []
    sink_id = l.add(lambda message: errors.append(str(message)), level='ERROR')
    try:
        with start_blocking_portal('asyncio') as portal:
            server = DevHttpServer(FastAPI(), portal, DevServerConfig(port=port))
            server.start()
            _wait_for(lambda: any('启动/运行失败' in m for m in errors))
            server.stop()
    finally:
        l.remove(sink_id)
        blocker.close()
