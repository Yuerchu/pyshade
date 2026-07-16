"""pyshade.shell 双形态:factory 选择、context 传参、dist 解析、smoke 回调(fake 模块,不起 GUI)。"""

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from pyshade.app import ShadeApp
from pyshade.components import Text
from pyshade.page import Page
from pyshade.shell import run


class ShellProbePage(Page):
    hello = Text('shell')


def _app() -> ShadeApp:
    return ShadeApp(title='Shell Probe', pages=[ShellProbePage])


class _FakeTauriApp:
    def __init__(self, record: dict[str, Any]) -> None:
        self._record = record

    def run_return(self, callback: Any = None) -> int:
        self._record['run_callback'] = callback
        return 0


class _FakeBuilder:
    def __init__(self, record: dict[str, Any]) -> None:
        self._record = record

    def build(self, *, context: Any, invoke_handler: Any) -> _FakeTauriApp:
        self._record['context'] = context
        self._record['invoke_handler'] = invoke_handler
        return _FakeTauriApp(self._record)


def _install_fake_wheel(monkeypatch: pytest.MonkeyPatch, record: dict[str, Any]) -> None:
    lib = types.ModuleType('pytauri_wheel.lib')

    def builder_factory() -> _FakeBuilder:
        return _FakeBuilder(record)

    def context_factory(config_dir: Path, *, tauri_config: dict[str, Any]) -> dict[str, Any]:
        record['config_dir'] = config_dir
        record['tauri_config'] = tauri_config
        return {'fake': 'context'}

    lib.builder_factory = builder_factory  # pyright: ignore[reportAttributeAccessIssue]
    lib.context_factory = context_factory  # pyright: ignore[reportAttributeAccessIssue]
    pkg = types.ModuleType('pytauri_wheel')
    monkeypatch.setitem(sys.modules, 'pytauri_wheel', pkg)
    monkeypatch.setitem(sys.modules, 'pytauri_wheel.lib', lib)


def _install_fake_standalone(monkeypatch: pytest.MonkeyPatch, record: dict[str, Any]) -> None:
    fake = types.ModuleType('pytauri')

    def builder_factory() -> _FakeBuilder:
        return _FakeBuilder(record)

    def context_factory() -> dict[str, Any]:
        record['context_args'] = ()
        return {'fake': 'standalone-context'}

    class _Ready: ...

    run_event = types.SimpleNamespace(Ready=_Ready)
    fake.builder_factory = builder_factory  # pyright: ignore[reportAttributeAccessIssue]
    fake.context_factory = context_factory  # pyright: ignore[reportAttributeAccessIssue]
    fake.RunEvent = run_event  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, 'pytauri', fake)
    monkeypatch.setattr(sys, '_pytauri_standalone', True, raising=False)


class TestRelativeFrontendDist:
    @pytest.mark.skipif(sys.platform != 'win32', reason='跨盘符语义仅 Windows')
    def test_cross_drive_gives_clear_error(self, tmp_path: Path) -> None:
        from pyshade.shell import relative_frontend_dist

        other_drive = Path('Q:/pyshade-dist')  # 假定不存在的盘符:relpath 不触盘,仅字符串运算
        with pytest.raises(SystemExit, match='同一盘符'):
            relative_frontend_dist(other_drive, tmp_path)

    def test_same_root_relative(self, tmp_path: Path) -> None:
        from pyshade.shell import relative_frontend_dist

        assert relative_frontend_dist(tmp_path / 'dist', tmp_path / 'cfg') == '../dist'


class TestWheelMode:
    def test_dist_baked_as_relative_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        record: dict[str, Any] = {}
        _install_fake_wheel(monkeypatch, record)
        config_dir = tmp_path / 'cfg'
        config_dir.mkdir()
        dist = tmp_path / 'dist'
        dist.mkdir()
        (dist / 'index.html').write_text('<html></html>', encoding='utf-8')

        assert run(_app(), config_dir=config_dir, dist_dir=dist) == 0
        assert record['config_dir'] == config_dir.absolute()
        assert record['tauri_config'] == {'build': {'frontendDist': '../dist'}}
        assert record['run_callback'] is None

    def test_env_dist_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        record: dict[str, Any] = {}
        _install_fake_wheel(monkeypatch, record)
        config_dir = tmp_path / 'cfg'
        config_dir.mkdir()
        env_dist = tmp_path / 'other-dist'
        env_dist.mkdir()
        (env_dist / 'index.html').write_text('x', encoding='utf-8')
        monkeypatch.setenv('PYSHADE_DIST', str(env_dist))

        run(_app(), config_dir=config_dir, dist_dir=None)
        assert record['tauri_config'] == {'build': {'frontendDist': '../other-dist'}}

    def test_missing_dist_rejected(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        record: dict[str, Any] = {}
        _install_fake_wheel(monkeypatch, record)
        with pytest.raises(SystemExit, match='缺少前端产物目录'):
            run(_app(), config_dir=tmp_path)

    def test_dev_mode_points_to_vite(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        record: dict[str, Any] = {}
        _install_fake_wheel(monkeypatch, record)
        monkeypatch.setenv('PYSHADE_DEV', '1')

        class _FakeDevServer:
            def __init__(self, app: Any, portal: Any) -> None: ...
            def start(self) -> None:
                record['dev_started'] = True

            def stop(self) -> None:
                record['dev_stopped'] = True

        from pyshade.asgi import _dev

        monkeypatch.setattr(_dev, 'DevHttpServer', _FakeDevServer)
        run(_app(), config_dir=tmp_path)
        assert record['tauri_config'] == {'build': {'frontendDist': 'http://localhost:5173'}}
        assert record.get('dev_started') and record.get('dev_stopped')


class TestStandaloneMode:
    def test_context_factory_called_without_args(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        record: dict[str, Any] = {}
        _install_fake_standalone(monkeypatch, record)
        assert run(_app(), config_dir=tmp_path) == 0
        assert record['context_args'] == ()
        assert record['context'] == {'fake': 'standalone-context'}

    def test_dev_env_ignored_in_standalone(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        record: dict[str, Any] = {}
        _install_fake_standalone(monkeypatch, record)
        monkeypatch.setenv('PYSHADE_DEV', '1')
        run(_app(), config_dir=tmp_path)
        assert 'tauri_config' not in record  # 不走 wheel 分支

    def test_smoke_registers_ready_callback(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        record: dict[str, Any] = {}
        _install_fake_standalone(monkeypatch, record)
        monkeypatch.setenv('PYSHADE_SMOKE', '1')
        run(_app(), config_dir=tmp_path)
        assert callable(record['run_callback'])
