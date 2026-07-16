"""生产 web dispatcher(design.md §3.10 web target):

- `/_shade/*` → 用户 FastAPI app(事件 + SSE 推送;lifespan 一并转发);
- 其余 → dist 静态三件套(html=True,`/` 即 index.html;hash 路由无需 SPA fallback)。

共享语义如实声明:ServerState 是进程级单例(§3.3),单进程 serve 下多浏览器客户端
共享同一份状态宇宙(请求外变更经 PatchBus 广播、重连快照收敛);per-visitor session
隔离是独立工作线(§6)。读多写少的站点(文档站)可直接用。
"""

from pathlib import Path
from typing import Any

from loguru import logger as l
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from pyshade.asgi._types import ASGIApp, Receive, Scope, Send


async def _plain_error(send: Send, status: int) -> None:
    await send(
        {
            'type': 'http.response.start',
            'status': status,
            'headers': [(b'content-type', b'text/plain; charset=utf-8')],
        }
    )
    await send({'type': 'http.response.body', 'body': str(status).encode()})


def make_web_asgi(user_app: ASGIApp, dist_dir: Path) -> ASGIApp:
    """静态 + `/_shade/*` 二路分发;dev dispatcher 在此之上叠 dev 专有路由。"""
    static = StaticFiles(directory=dist_dir, html=True)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'lifespan':
            await user_app(scope, receive, send)
            return
        path: Any = scope.get('path', '')
        if isinstance(path, str) and path.startswith('/_shade/'):
            await user_app(scope, receive, send)
            return
        try:
            await static(scope, receive, send)
        except StarletteHTTPException as exc:
            # 裸 ASGI 无 ExceptionMiddleware:StaticFiles 的 404/405 在响应开始前抛出,可安全转纯响应
            await _plain_error(send, exc.status_code)

    return app


def run_serve(spec: str, *, host: str = '127.0.0.1', port: int = 8000, workdir: Path | None = None) -> int:
    """`pyshade serve` 实现:bundle(生产)→ uvicorn 起 web dispatcher。"""
    import uvicorn

    from pyshade.bundler import bundle_app
    from pyshade.cli import load_app
    from pyshade.events import EventRegistry
    from pyshade.runtime import build_fastapi_app

    work = (workdir or Path('.pyshade/serve')).absolute()
    dist = work / 'dist'
    app = load_app(spec)
    bundle_app(app, dist, workdir=work / 'build')
    registry = EventRegistry.from_app(app)
    fastapi_app = build_fastapi_app(registry, title=app.title)
    dispatcher = make_web_asgi(fastapi_app, dist)
    l.info("pyshade serve: http://{}:{}(单进程;多客户端共享 ServerState,design.md §3.10)", host, port)
    uvicorn.run(dispatcher, host=host, port=port, log_level='info', lifespan='on')
    return 0
