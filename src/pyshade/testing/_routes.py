"""测试路由:/_shade/_test/*;零 pytauri 依赖,httpx ASGITransport 可直接单测。"""

import hashlib
from collections.abc import AsyncIterator
from typing import Any, Protocol

import anyio
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from pyshade.testing._collector import ReportCollector

_PATTERN = bytes(range(256))


class HarnessActions(Protocol):
    """harness 提供给测试路由的原生动作(case 5 关窗)。"""

    def close_window(self) -> None: ...


def mount_test_routes(app: FastAPI, collector: ReportCollector, *, actions: HarnessActions | None = None) -> None:
    """挂载 /_shade/_test/*;仅测试模式调用,生产 app 永不挂载。"""

    prefix = '/_shade/_test'

    @app.post(f'{prefix}/hello')
    async def hello(request: Request) -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
        collector.on_hello(await request.json())
        return {'ok': True}

    @app.post(f'{prefix}/heartbeat')
    async def heartbeat(request: Request) -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
        collector.on_heartbeat(await request.json())
        return {'ok': True}

    @app.post(f'{prefix}/report')
    async def report(request: Request) -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
        collector.on_report(await request.json())
        return {'ok': True}

    @app.api_route(f'{prefix}/echo/{{rest:path}}', methods=['GET', 'POST'])
    async def echo(request: Request, rest: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        body = await request.body()
        return {
            'method': request.method,
            'path': request.url.path,
            'query': str(request.url.query),
            'headers': dict(request.headers.items()),
            'body_len': len(body),
            'body_sha256': hashlib.sha256(body).hexdigest(),
        }

    @app.get(f'{prefix}/blob')
    async def blob(size: int) -> Response:  # pyright: ignore[reportUnusedFunction]
        content = (_PATTERN * (size // 256 + 1))[:size]
        return Response(content=content, media_type='application/octet-stream')

    @app.post(f'{prefix}/sink')
    async def sink(request: Request) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        body = await request.body()
        return {'len': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

    @app.get(f'{prefix}/stream_fast')
    async def stream_fast(frames: int = 20) -> StreamingResponse:  # pyright: ignore[reportUnusedFunction]
        # 无 await 的同步循环:最大化"帧早于 invoke resolve 抵达前端"的竞态窗口(case 2)
        async def gen() -> AsyncIterator[bytes]:
            for i in range(frames):
                yield f'{i:06d}:'.encode() + bytes((i % 256,)) * 64

        return StreamingResponse(gen(), media_type='application/octet-stream')

    @app.get(f'{prefix}/stream_slow')
    async def stream_slow(frames: int = 100, delay_ms: int = 100) -> StreamingResponse:  # pyright: ignore[reportUnusedFunction]
        async def gen() -> AsyncIterator[bytes]:
            for i in range(frames):
                yield f'{i:06d}:'.encode().ljust(32, b'.')
                await anyio.sleep(delay_ms / 1000)

        return StreamingResponse(gen(), media_type='application/octet-stream')

    @app.post(f'{prefix}/close_window')
    async def close_window() -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
        if actions is not None:
            actions.close_window()
        return {'ok': True}
