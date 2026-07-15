"""运行时装配:__main__ 与测试共用的构造入口。"""

from fastapi import FastAPI

from component_gallery.app import app
from pyshade.events import EventRegistry
from pyshade.runtime import build_fastapi_app


def build_runtime() -> tuple[EventRegistry, FastAPI]:
    registry = EventRegistry.from_app(app)
    fastapi_app = build_fastapi_app(registry, title=app.title)
    return registry, fastapi_app
