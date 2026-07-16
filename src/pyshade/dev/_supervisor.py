"""dev supervisor(父进程,不 import 用户代码):

watchfiles 监听用户源码 → terminate 旧 worker → spawn 新 worker(整代重启)。
子进程重启是硬约束推出的:同进程重 import 同名 ServerState 类会撞 _STATE_CLASSES
注册表,且 handler 引用/EventRegistry/单例都需要归零。
spawner/watcher 可注入(单测不起进程不碰文件系统)。
"""

import importlib.util
import subprocess
import sys
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from loguru import logger as l
from watchfiles import PythonFilter, watch

Spawner = Callable[[list[str]], 'subprocess.Popen[bytes]']
Watcher = Callable[..., Iterator[Any]]


def worker_command(spec: str, *, port: int, workdir: Path) -> list[str]:
    """worker 启动命令;sys.executable 即当前 venv 解释器(不落裸 python)。"""
    return [sys.executable, '-m', 'pyshade.dev', spec, '--port', str(port), '--workdir', str(workdir)]


def resolve_watch_paths(spec: str, extra: Iterable[Path] = ()) -> list[Path]:
    """从 app spec 的顶层包名定位源码目录(find_spec 只定位不执行);失败回退 cwd。"""
    top = spec.split(':')[0].split('.')[0]
    paths: list[Path] = []
    try:
        module_spec = importlib.util.find_spec(top)
    except (ImportError, ValueError):
        module_spec = None
    if module_spec is not None and module_spec.submodule_search_locations:
        paths.extend(Path(location) for location in module_spec.submodule_search_locations)
    if not paths:
        paths.append(Path.cwd())
        l.warning("pyshade dev: 无法定位包 {!r} 的源码目录,回退监听当前目录(--watch 可显式指定)", top)
    paths.extend(extra)
    return paths


def _default_spawner(command: list[str]) -> 'subprocess.Popen[bytes]':
    # stdout/stderr 直通终端:编译错误/uvicorn 日志裸露给用户
    return subprocess.Popen(command)


def _terminate(worker: 'subprocess.Popen[bytes]') -> None:
    if worker.poll() is not None:
        return
    worker.terminate()
    try:
        worker.wait(timeout=10)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait(timeout=10)


def supervise(
    spec: str,
    *,
    port: int,
    workdir: Path,
    watch_paths: list[Path],
    spawner: Spawner = _default_spawner,
    watcher: Watcher | None = None,
) -> int:
    """常驻循环:变更即整代重启;Ctrl+C 收尾 worker 后退出。"""
    command = worker_command(spec, port=port, workdir=workdir)
    active_watcher = watcher if watcher is not None else watch
    worker = spawner(command)
    crash_reported = False
    l.info("pyshade dev: 监听 {}(Ctrl+C 退出)", [str(p) for p in watch_paths])
    try:
        # rust_timeout+yield_on_timeout:每秒产出一次空集心跳,借此感知 worker 崩溃
        # (端口占用/启动期异常此前静默——supervisor 空等文件变更,用户毫无提示)
        for changes in active_watcher(
            *watch_paths, watch_filter=PythonFilter(), rust_timeout=1000, yield_on_timeout=True
        ):
            if not changes:  # 心跳帧
                code = worker.poll()
                if code is not None and not crash_reported:
                    crash_reported = True
                    l.error(
                        "pyshade dev: worker 已退出(exit {});常见原因:端口 {} 被占用或启动期异常"
                        "(错误见上方日志)→ 修复后保存源码即自动重启,或 Ctrl+C 退出",
                        code,
                        port,
                    )
                continue
            changed = sorted({Path(str(item[1])).name for item in changes})
            l.info("pyshade dev: 变更 {} → 重启 worker", changed)
            _terminate(worker)
            worker = spawner(command)
            crash_reported = False
    except KeyboardInterrupt:
        pass
    finally:
        _terminate(worker)
    return 0
