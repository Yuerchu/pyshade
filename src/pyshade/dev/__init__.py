"""pyshade dev(M3):面向最终用户的浏览器开发循环。

supervisor(本包,不 import 用户代码)+ worker(`python -m pyshade.dev`,每代全新进程)。
改动即整代重启:watchfiles 命中 → terminate → respawn → 浏览器经 generation SSE 自动 reload。
原生窗口不进 dev loop(窗口进程即 Python 进程,重启必关窗;PYSHADE_DEV 两态照旧),
窗口热重载记 design.md §6 开放问题。
"""

import webbrowser
from pathlib import Path

from loguru import logger as l

from pyshade.dev._supervisor import resolve_watch_paths, supervise

__all__ = ['run_dev']


def run_dev(
    spec: str,
    *,
    port: int = 8765,
    open_browser: bool = False,
    watch: list[Path] | None = None,
    workdir: Path = Path('.pyshade/dev'),
) -> int:
    watch_paths = resolve_watch_paths(spec, watch or [])
    url = f'http://127.0.0.1:{port}'
    l.info("pyshade dev: {} → {}", spec, url)
    if open_browser:
        webbrowser.open(url)
    return supervise(spec, port=port, workdir=workdir.absolute(), watch_paths=watch_paths)
