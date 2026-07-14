"""运行时装配:__main__ 与测试 harness 共用的构造入口。"""

from fastapi import FastAPI

from login_form.app import app
from login_form.handlers import bench_echo
from pyshade.events import EventRegistry
from pyshade.runtime import build_fastapi_app


def build_runtime() -> tuple[EventRegistry, FastAPI]:
    registry = EventRegistry.from_app(app, extra_handlers={'bench_echo': bench_echo})
    fastapi_app = build_fastapi_app(registry, title=app.title)
    return registry, fastapi_app
