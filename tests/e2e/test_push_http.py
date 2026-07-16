"""GET /_shade/push 的 HTTP SSE 冒烟(M4 补缺口):此前该通路只被 IPC 流式分支间接覆盖。

web serve(uvicorn)模式下浏览器直接消费此 SSE。ASGITransport 会缓冲无限流(M1 教训),
故原始 ASGI 驱动:首帧快照 → 发布一条 patch → 收到第二帧即断连。
"""

import json
from collections.abc import MutableMapping
from typing import Any

import anyio
import pytest
from fastapi import FastAPI

from pyshade.push import PatchBus, mount_push_route

pytestmark = pytest.mark.anyio

_PATCH = {'target': '$s:PushSmoke', 'props': {'tick': 1}}


async def test_push_sse_snapshot_then_patch() -> None:
    # 手工组 app 只挂一次 push 路由:build_fastapi_app 内部自带一份 bus,
    # 同 path 重挂后路由仍是第一个生效,发布到第二条 bus 无人订阅(实测教训)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    bus = mount_push_route(app, bus=PatchBus())

    scope: dict[str, Any] = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': 'GET',
        'scheme': 'http',
        'path': '/_shade/push',
        'raw_path': b'/_shade/push',
        'query_string': b'',
        'root_path': '',
        'headers': [],
        'client': ('test', 1),
        'server': ('test', 80),
    }

    start_messages: list[MutableMapping[str, Any]] = []
    data_frames: list[bytes] = []
    published = False
    done = anyio.Event()

    async def receive() -> MutableMapping[str, Any]:
        await done.wait()
        return {'type': 'http.disconnect'}

    async def send(message: MutableMapping[str, Any]) -> None:
        nonlocal published
        if message['type'] == 'http.response.start':
            start_messages.append(message)
            return
        if message['type'] != 'http.response.body':
            return
        body: bytes = message.get('body', b'')
        for chunk in body.split(b'\n\n'):
            if chunk.startswith(b'data: '):
                data_frames.append(chunk[len(b'data: ') :])
        if data_frames and not published:
            published = True
            bus.publish(dict(_PATCH))  # 首帧(快照)已出 → 订阅者就位,发布必达
        if len(data_frames) >= 2:
            done.set()

    with anyio.fail_after(5):
        await app(scope, receive, send)

    assert start_messages and start_messages[0]['status'] == 200
    headers = dict(start_messages[0]['headers'])
    assert headers[b'content-type'].startswith(b'text/event-stream')

    snapshot = json.loads(data_frames[0])
    assert 'patches' in snapshot  # 首帧:全局 ServerState 快照(内容随测试进程内注册的状态而定)
    assert json.loads(data_frames[1]) == {'patches': [_PATCH]}
