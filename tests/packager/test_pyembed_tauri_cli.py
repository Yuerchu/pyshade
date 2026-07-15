"""安装命令组装(uv/pip 双路)、tauri build 命令组装、前置体检汇总(不联网不装 Rust)。"""

from pathlib import Path

import pytest

from pyshade.packager import _tauri_cli
from pyshade.packager._pyembed import install_command
from pyshade.packager._tauri_cli import preflight_issues, tauri_build_command


class TestInstallCommand:
    def test_uv_command_shape(self) -> None:
        python = Path('pyembed') / 'python' / 'python.exe'
        project = Path('proj')
        command = install_command(
            python,
            project,
            dist_name='task-board',
            extra_requirements=('wheels/pyshade-0.1.0-py3-none-any.whl',),
            uv_path='uv',
        )
        assert command == [
            'uv',
            'pip',
            'install',
            '--exact',
            f'--python={python}',
            '--reinstall-package=task-board',
            str(project),
            'wheels/pyshade-0.1.0-py3-none-any.whl',
        ]

    def test_pip_fallback_without_exact(self) -> None:
        python = Path('pyembed') / 'python' / 'python.exe'
        command = install_command(python, Path('proj'), dist_name='task-board', uv_path=None)
        assert command[:5] == [str(python), '-m', 'pip', 'install', '--upgrade']
        assert '--exact' not in command


class TestTauriBuildCommand:
    def test_shape(self) -> None:
        assert tauri_build_command(bundles=('nsis', 'msi'), profile='bundle-release') == [
            'cargo-tauri',
            'build',
            '--config',
            'src-tauri/tauri.bundle.json',
            '--bundles',
            'nsis,msi',
            '--',
            '--profile',
            'bundle-release',
        ]


def _which_none(name: str) -> str | None:
    return None


def _which_fake(name: str) -> str:
    return f'C:/fake/{name}.exe'


class _VersionResult:
    def __init__(self, stdout: str) -> None:
        self.returncode = 0
        self.stdout = stdout


def _fake_run(stdout: str) -> object:
    def runner(*args: object, **kwargs: object) -> _VersionResult:
        return _VersionResult(stdout)

    return runner


class TestPreflight:
    def test_all_missing_aggregated(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(_tauri_cli.shutil, 'which', _which_none)
        issues = preflight_issues(tmp_path)
        joined = '\n'.join(issues)
        assert len(issues) == 3  # src-tauri 缺 + cargo 缺 + tauri-cli 缺,一次性汇总
        assert 'pyshade init' in joined
        assert 'rustup.rs' in joined
        assert "cargo install tauri-cli" in joined

    def test_ready_project_no_issues(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        (tmp_path / 'src-tauri').mkdir()
        (tmp_path / 'src-tauri' / 'tauri.conf.json').write_text('{}', encoding='utf-8')
        monkeypatch.setattr(_tauri_cli.shutil, 'which', _which_fake)
        monkeypatch.setattr(_tauri_cli.subprocess, 'run', _fake_run('tauri-cli 2.10.1'))
        assert preflight_issues(tmp_path) == []

    def test_wrong_tauri_cli_major(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        (tmp_path / 'src-tauri').mkdir()
        (tmp_path / 'src-tauri' / 'tauri.conf.json').write_text('{}', encoding='utf-8')
        monkeypatch.setattr(_tauri_cli.shutil, 'which', _which_fake)
        monkeypatch.setattr(_tauri_cli.subprocess, 'run', _fake_run('tauri-cli 1.5.0'))
        issues = preflight_issues(tmp_path)
        assert len(issues) == 1
        assert '版本不符' in issues[0]
