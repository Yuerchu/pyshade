"""dev supervisor:worker 命令组装、监听目录解析、变更即整代重启(fake spawner/watcher)。"""

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pyshade.dev._supervisor import resolve_watch_paths, supervise, worker_command


class TestWorkerCommand:
    def test_uses_current_interpreter(self) -> None:
        command = worker_command('task_board.app:app', port=9000, workdir=Path('.pyshade/dev'))
        assert command[0] == sys.executable  # 项目 venv 解释器,不落裸 python
        assert command[1:4] == ['-m', 'pyshade.dev', 'task_board.app:app']
        assert '--port' in command and '9000' in command


class TestResolveWatchPaths:
    def test_resolves_package_source_dir(self) -> None:
        paths = resolve_watch_paths('task_board.app:app')
        assert any(p.name == 'task_board' for p in paths)

    def test_unknown_package_falls_back_to_cwd(self) -> None:
        paths = resolve_watch_paths('no_such_pkg_xyz.app:app')
        assert paths == [Path.cwd()]

    def test_extra_paths_appended(self, tmp_path: Path) -> None:
        paths = resolve_watch_paths('task_board.app:app', [tmp_path])
        assert paths[-1] == tmp_path


class _FakeWorker:
    def __init__(self, log: list[str], index: int) -> None:
        self._log = log
        self._index = index
        self._alive = True

    def poll(self) -> int | None:
        return None if self._alive else 0

    def terminate(self) -> None:
        self._log.append(f'terminate:{self._index}')
        self._alive = False

    def kill(self) -> None:
        self._log.append(f'kill:{self._index}')
        self._alive = False

    def wait(self, timeout: float | None = None) -> int:
        return 0


class TestSupervise:
    def test_change_triggers_generation_restart(self, tmp_path: Path) -> None:
        log: list[str] = []
        counter = {'n': 0}

        def spawner(command: list[str]) -> Any:
            counter['n'] += 1
            log.append(f'spawn:{counter["n"]}')
            return _FakeWorker(log, counter['n'])

        def watcher(*paths: Path, **kwargs: Any) -> Iterator[set[tuple[int, str]]]:
            yield {(1, str(tmp_path / 'pages.py'))}
            raise KeyboardInterrupt  # 模拟 Ctrl+C 收尾

        exit_code = supervise(
            'demo.app:app',
            port=8765,
            workdir=tmp_path,
            watch_paths=[tmp_path],
            spawner=spawner,
            watcher=watcher,
        )
        assert exit_code == 0
        # 首代 spawn → 变更 terminate+respawn → Ctrl+C 终代 terminate
        assert log == ['spawn:1', 'terminate:1', 'spawn:2', 'terminate:2']
