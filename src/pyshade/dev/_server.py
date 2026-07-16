"""dev dispatcher(纯函数,httpx ASGITransport 可测):

- `/_shade/dev/events`:SSE,首帧 `{"generation": ...}`,之后周期 ping 保活;
- `/_shade/dev/client.js`:内置重载客户端(断线重连,generation 变化即整页 reload);
- 其余(含 lifespan)委托生产 web dispatcher(web/_serve.make_web_asgi):
  `/_shade/*` → 用户 app,静态 → dist。
"""

import json
from pathlib import Path
from typing import Any

import anyio

from pyshade.asgi._types import ASGIApp, Receive, Scope, Send
from pyshade.web import make_web_asgi

_PING_INTERVAL_S = 15.0

DEV_CLIENT_JS = """\
// pyshade dev 重载客户端:worker 重启 → generation 变化 → 整页 reload
(() => {
  let known = null;
  const connect = () => {
    const es = new EventSource("/_shade/dev/events");
    es.onmessage = (event) => {
      const { generation } = JSON.parse(event.data);
      if (known === null) {
        known = generation;
      } else if (generation !== known) {
        location.reload();
      }
    };
    es.onerror = () => {
      es.close();
      setTimeout(connect, 500);
    };
  };
  connect();
})();
"""


def inject_dev_client(html: str) -> str:
    """在 </head> 前注入重载客户端(幂等)。"""
    if '/_shade/dev/client.js' in html:
        return html
    tag = '<script src="/_shade/dev/client.js"></script>'
    if '</head>' in html:
        return html.replace('</head>', f'  {tag}\n  </head>', 1)
    return f'{tag}\n{html}'


async def _send_text(send: Send, status: int, content_type: bytes, body: bytes) -> None:
    await send({'type': 'http.response.start', 'status': status, 'headers': [(b'content-type', content_type)]})
    await send({'type': 'http.response.body', 'body': body})


async def _sse_events(receive: Receive, send: Send, generation: str) -> None:
    await send(
        {
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-type', b'text/event-stream'), (b'cache-control', b'no-cache')],
        }
    )
    first = f'data: {json.dumps({"generation": generation})}\n\n'.encode()
    await send({'type': 'http.response.body', 'body': first, 'more_body': True})
    while True:
        disconnected = False
        with anyio.move_on_after(_PING_INTERVAL_S):
            message = await receive()
            disconnected = message['type'] == 'http.disconnect'
        if disconnected:
            return
        await send({'type': 'http.response.body', 'body': b': ping\n\n', 'more_body': True})


def make_dev_asgi(user_app: ASGIApp, dist_dir: Path, generation: str) -> ASGIApp:
    base = make_web_asgi(user_app, dist_dir)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        path: Any = scope.get('path', '') if scope['type'] == 'http' else ''
        if path == '/_shade/dev/events':
            await _sse_events(receive, send, generation)
        elif path == '/_shade/dev/client.js':
            await _send_text(send, 200, b'application/javascript; charset=utf-8', DEV_CLIENT_JS.encode())
        else:
            await base(scope, receive, send)

    return app
