"""dev worker(每代一个全新进程,`python -m pyshade.dev` 拉起):

load_app → bundle_app(dev)→ 注入重载客户端 → uvicorn 起 dispatcher。
全新解释器保证 _STATE_CLASSES/EventRegistry 干净——这是子进程整代重启模型的动因。
先编译再绑端口:编译失败端口保持死亡,浏览器静默重连,终端裸露 CompileError,修好自愈。
"""

import argparse
import sys
import time
import uuid
from pathlib import Path

from loguru import logger as l


def worker_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='pyshade.dev', description='pyshade dev worker(内部)')
    parser.add_argument('app')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--workdir', default='.pyshade/dev')
    args = parser.parse_args(argv)

    import uvicorn

    from pyshade.bundler import bundle_app
    from pyshade.cli import load_app
    from pyshade.dev._server import inject_dev_client, make_dev_asgi
    from pyshade.events import EventRegistry
    from pyshade.runtime import build_fastapi_app

    workdir = Path(args.workdir).absolute()
    dist = workdir / 'dist'

    # 阶段计时:dev loop 延迟基线(design.md §4;M4 起 esbuild 命中内容哈希即跳过)
    t0 = time.monotonic()
    app = load_app(args.app)
    t1 = time.monotonic()
    bundle = bundle_app(app, dist, dev=True, workdir=workdir / 'build')

    index = dist / 'index.html'
    index.write_text(inject_dev_client(index.read_text(encoding='utf-8')), encoding='utf-8', newline='\n')

    registry = EventRegistry.from_app(app)
    fastapi_app = build_fastapi_app(registry, title=app.title)
    generation = uuid.uuid4().hex
    dispatcher = make_dev_asgi(fastapi_app, dist, generation)
    l.info(
        "pyshade dev: 就绪 http://127.0.0.1:{}(import {:.0f}ms / bundle {:.0f}ms = "
        "staging {:.0f} + compile {:.0f} + esbuild {:.0f}{},generation {})",
        args.port,
        (t1 - t0) * 1000,
        bundle.duration_ms,
        bundle.staging_ms,
        bundle.compile_ms,
        bundle.esbuild_ms,
        ' [skipped]' if bundle.esbuild_skipped else '',
        generation[:8],
    )

    # timeout_graceful_shutdown=1:dev SSE(重载事件/push)常驻不关,默认 None 会让优雅
    # 关闭无限等 → POSIX 下 supervisor 的 SIGTERM 固定撑满 wait(10) 再 SIGKILL,
    # 每次热重载凭空 +10s(Windows 硬杀不可见,主平台外的第一天体验)
    uvicorn.run(
        dispatcher, host='127.0.0.1', port=args.port, log_level='warning', lifespan='on', timeout_graceful_shutdown=1
    )
    return 0


def main() -> int:
    return worker_main(sys.argv[1:])
