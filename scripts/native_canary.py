"""Phase 0 canary:验证 R1(visible:false 下 WebView2 执行 JS)+ ASGI over IPC 真机首通。

自包含:临时目录生成 Tauri.toml / capabilities / 最小前端页面,不依赖 example。
用法:uv run python scripts/native_canary.py
退出码 0 = 验证通过;CI 首绿后本脚本删除(计划 Phase 1f)。
"""

import sys
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from anyio.from_thread import start_blocking_portal
from fastapi import FastAPI, Request
from loguru import logger as l

from pyshade.asgi import AsgiIpcAdapter

TAURI_TOML = """\
"$schema" = "https://schema.tauri.app/config/2"
productName = "pyshade-canary"
version = "0.1.0"
identifier = "cn.yuxiaoqiu.pyshade.canary"

[build]
frontendDist = "./frontend"

[app]
withGlobalTauri = true

[[app.windows]]
title = "pyshade canary"
width = 320
height = 240
visible = false
"""

CAPABILITIES_TOML = """\
identifier = "default"
description = "canary capability"
windows = ["main"]
permissions = ["core:default", "pytauri:default"]
"""

INDEX_HTML = """\
<!doctype html>
<html><head><meta charset="utf-8"><title>canary</title></head>
<body><div id="status">canary page loaded</div></body></html>
"""

# 幂等 guard + 裸 invoke(shadeFetch 尚未存在,Phase 1a 才建)
INJECT_JS = """\
(function () {
  if (window.__pyshadeCanaryDone) return;
  window.__pyshadeCanaryDone = true;
  const payload = new TextEncoder().encode(JSON.stringify({
    visibility: document.visibilityState,
    hasTauri: '__TAURI__' in window,
    userAgent: navigator.userAgent,
  }));
  window.__TAURI__.core.invoke('plugin:pytauri|pyfunc', payload, {
    headers: {
      pyfunc: '__pyshade_asgi__',
      'x-pyshade-method': 'POST',
      'x-pyshade-path': '/canary/hello',
      'content-type': 'application/json',
    },
  }).then(
    function () { document.getElementById('status').textContent = 'hello ok'; },
    function (e) { document.getElementById('status').textContent = 'hello failed: ' + e; }
  );
})();
"""

HELLO_TIMEOUT_S = 30.0


def main() -> int:
    hello_received = threading.Event()
    hello_payload: dict[str, Any] = {}

    fastapi_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @fastapi_app.post('/canary/hello')
    async def canary_hello(request: Request) -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
        hello_payload.update(await request.json())
        hello_received.set()
        return {'ok': True}

    with TemporaryDirectory(prefix='pyshade-canary-') as tmp:
        src_dir = Path(tmp)
        (src_dir / 'Tauri.toml').write_text(TAURI_TOML, encoding='utf-8')
        (src_dir / 'capabilities').mkdir()
        (src_dir / 'capabilities' / 'default.toml').write_text(CAPABILITIES_TOML, encoding='utf-8')
        (src_dir / 'frontend').mkdir()
        (src_dir / 'frontend' / 'index.html').write_text(INDEX_HTML, encoding='utf-8')

        from pytauri import Manager, RunEvent
        from pytauri_wheel.lib import builder_factory, context_factory

        with start_blocking_portal('asyncio') as portal:
            adapter = AsgiIpcAdapter(fastapi_app, portal)
            with adapter.lifespan():
                app = builder_factory().build(
                    context=context_factory(src_dir),
                    invoke_handler=adapter.invoke_handler(),
                )
                app_handle = app.handle()

                def injector() -> None:
                    start = time.monotonic()
                    while not hello_received.wait(timeout=2.0):
                        if time.monotonic() - start > HELLO_TIMEOUT_S:
                            l.error("canary: hello 超时({}s),eval 未执行或 IPC 不通", HELLO_TIMEOUT_S)
                            app_handle.exit(1)
                            return
                        window = Manager.get_webview_window(app_handle, 'main')
                        if window is not None:
                            try:
                                window.eval(INJECT_JS)
                            except Exception as exc:
                                l.warning("canary: eval 失败,重试中: {}", exc)
                    app_handle.exit(0)

                def on_event(handle: Any, event: Any) -> None:
                    if isinstance(event, RunEvent.Ready):
                        threading.Thread(target=injector, daemon=True).start()

                exit_code = app.run_return(on_event)

    if hello_received.is_set():
        print(
            f"R1 verified: visibility={hello_payload.get('visibility')!r}, "
            f"hasTauri={hello_payload.get('hasTauri')}, ua={hello_payload.get('userAgent', '')[:80]}"
        )
        return 0
    print("canary FAILED: hello never received", file=sys.stderr)
    return exit_code or 1


if __name__ == '__main__':
    sys.exit(main())
