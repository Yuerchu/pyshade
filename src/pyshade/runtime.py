"""运行时装配:EventRegistry → FastAPI 路由(计划 Part B 接缝约定)。

- 事件路由固定在 `/_shade` 命名空间下,用户路由永不冲突;
- FastAPI 是实现细节:docs/redoc/openapi 路由默认不存在(design.md §3.7)。
"""

import inspect
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from pyshade.events import EventContext, EventRegistry, Update


def build_fastapi_app(registry: EventRegistry, *, title: str = 'pyshade') -> FastAPI:
    """构造承载事件路由的 FastAPI app;对最终用户不可见。"""
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)
    mount_event_routes(app, registry)
    return app


def mount_event_routes(app: FastAPI, registry: EventRegistry) -> None:
    """挂载 POST /_shade/event/{handler_id};响应 {"patches": [...]}(接缝约定 1)。"""

    @app.post('/_shade/event/{handler_id}')
    async def dispatch_event(handler_id: str, request: Request) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        entry = registry.get(handler_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"unknown handler: {handler_id}")
        body = await request.body()
        try:
            payload = EventContext.model_validate_json(body) if body else EventContext()
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        result = entry.handler(payload)
        if inspect.isawaitable(result):
            result = await result
        updates: list[Update] = []
        if result is not None:
            items: list[object] = list(result)
            if not all(isinstance(u, Update) for u in items):
                raise HTTPException(
                    status_code=500,
                    detail=f"handler {handler_id} 必须返回 list[Update] 或 None",
                )
            updates = [u for u in items if isinstance(u, Update)]
        return {'patches': [update.to_payload() for update in updates]}
