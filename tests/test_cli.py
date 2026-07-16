"""cli.load_app:cwd 导入语义(对齐 `python -m`)、报错指引、错误收敛。"""

import sys
from pathlib import Path
from typing import Any

import pytest

from pyshade.cli import _bundle, load_app  # pyright: ignore[reportPrivateUsage]  # CLI 白盒测试


class TestLoadApp:
    def test_cwd_added_to_sys_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 项目目录下 `pyshade bundle app:app`:console script 不含 cwd,此前直接报导入失败
        (tmp_path / 'demo_cli_app.py').write_text(
            'from pyshade.app import ShadeApp\n'
            'from pyshade.page import Page\n'
            'from pyshade.components import Text\n\n'
            'class CliProbePage(Page):\n'
            "    hello = Text('cli')\n\n"
            'app = ShadeApp(pages=[CliProbePage])\n',
            encoding='utf-8',
        )
        monkeypatch.chdir(tmp_path)
        try:
            app = load_app('demo_cli_app:app')
            assert app.pages[0].__name__ == 'CliProbePage'
        finally:
            sys.modules.pop('demo_cli_app', None)
            if str(tmp_path) in sys.path:
                sys.path.remove(str(tmp_path))

    def test_import_error_has_hint(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            load_app('no_such_module_xyz:app')
        assert exc_info.value.code == 1
        stderr = capsys.readouterr().err
        assert 'PYTHONPATH' in stderr

    def test_not_shade_app_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            load_app('json:dumps')
        assert '不是 ShadeApp 实例' in capsys.readouterr().err


class TestBundleErrorConvergence:
    def test_known_errors_exit_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        import argparse

        import pyshade.bundler as bundler
        from pyshade.bundler._esbuild import EsbuildAcquireError

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise EsbuildAcquireError("esbuild 下载失败(测试注入)")

        def fake_load(spec: str) -> object:
            return object()

        monkeypatch.setattr(bundler, 'bundle_app', boom)
        monkeypatch.setattr('pyshade.cli.load_app', fake_load)
        ns = argparse.Namespace(app='x:app', out=str(tmp_path / 'dist'), dev=False, workdir=str(tmp_path / 'work'))
        with pytest.raises(SystemExit) as exc_info:
            _bundle(ns)
        assert exc_info.value.code == 1
        assert '测试注入' in capsys.readouterr().err
