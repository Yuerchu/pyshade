"""package_app 编排:步骤顺序、增量跳过、体检失败汇总、产物收集(全步 stub,不联网不装 Rust)。"""

from pathlib import Path
from typing import Any

import pytest

import pyshade.packager as packager
from pyshade.packager import PackageResult, package_app
from pyshade.packager._cpython import cpython_triple, pyembed_stamp
from pyshade.packager._tauri_cli import TauriCliError


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / 'demo'
    (project / 'src' / 'demo_app').mkdir(parents=True)
    (project / 'src' / 'demo_app' / '__init__.py').write_text('', encoding='utf-8')
    (project / 'pyproject.toml').write_text('[project]\nname = "demo-app"\nversion = "0.2.0"\n', encoding='utf-8')
    src_tauri = project / 'src-tauri'
    src_tauri.mkdir()
    (src_tauri / 'tauri.conf.json').write_text('{"productName": "demo-app"}', encoding='utf-8')
    (src_tauri / 'Cargo.toml').write_text('[package]\nname = "demo-app"\n', encoding='utf-8')
    (src_tauri / 'frontend').mkdir()
    (src_tauri / 'frontend' / 'index.html').write_text('<html></html>', encoding='utf-8')
    return project


def _stub_steps(monkeypatch: pytest.MonkeyPatch, project: Path, calls: list[str]) -> None:
    def fake_preflight(project_dir: Path) -> list[str]:
        calls.append('preflight')
        return []

    def fake_ensure(*, version: str, release: str) -> Path:
        calls.append(f'ensure:{version}+{release}')
        return project / 'fake.tar.gz'

    def fake_extract(tarball: Path, pyembed_dir: Path, *, version: str, release: str) -> Path:
        calls.append('extract')
        python = packager.pyembed_python_path(pyembed_dir)
        python.parent.mkdir(parents=True, exist_ok=True)
        python.write_bytes(b'')
        stamp = pyembed_dir / '.pyshade-stamp'
        stamp.write_text(pyembed_stamp(cpython_triple(), version=version, release=release), encoding='utf-8')
        return python

    def fake_patch(pyembed_dir: Path) -> list[Path]:
        calls.append('patch')
        return []

    def fake_install(
        pyembed_python: Path, project_dir: Path, *, dist_name: str, extra_requirements: tuple[str, ...] = ()
    ) -> None:
        calls.append(f'install:{dist_name}')

    def fake_pollution(pyembed_python: Path) -> bool:
        calls.append('pollution-check')
        return False

    def fake_compile(pyembed_python: Path) -> None:
        calls.append('compileall')

    def fake_build(project_dir: Path, env: dict[str, str], *, bundles: tuple[str, ...], profile: str) -> None:
        calls.append(f'build:{",".join(bundles)}:{profile}')
        assert 'PYO3_PYTHON' in env
        nsis = project_dir / 'src-tauri' / 'target' / profile / 'bundle' / 'nsis'
        nsis.mkdir(parents=True, exist_ok=True)
        (nsis / 'demo-app_0.2.0_x64-setup.exe').write_bytes(b'installer')

    monkeypatch.setattr(packager, 'preflight_issues', fake_preflight)
    monkeypatch.setattr(packager, 'ensure_cpython_tarball', fake_ensure)
    monkeypatch.setattr(packager, 'extract_pyembed', fake_extract)
    monkeypatch.setattr(packager, 'patch_macos_dylib', fake_patch)
    monkeypatch.setattr(packager, 'install_project', fake_install)
    monkeypatch.setattr(packager, 'warn_if_wheel_polluted', fake_pollution)
    monkeypatch.setattr(packager, 'compile_bytecode', fake_compile)
    monkeypatch.setattr(packager, 'run_tauri_build', fake_build)


class TestOrchestration:
    def test_fresh_run_step_order(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        calls: list[str] = []
        _stub_steps(monkeypatch, project, calls)

        result = package_app(
            'demo_app.app:app',
            project,
            out_dir=tmp_path / 'out',
            bundles=('nsis',),
            skip_bundle=True,
        )
        assert isinstance(result, PackageResult)
        expected = [
            'preflight',
            f'ensure:{packager.CPYTHON_VERSION}+{packager.PBS_RELEASE}',
            'extract',
            'install:demo-app',
            'pollution-check',
            'compileall',
            'build:nsis:bundle-release',
        ]
        assert [c for c in calls if c != 'patch'] == expected  # patch 仅 darwin
        assert [p.name for p in result.artifacts] == ['demo-app_0.2.0_x64-setup.exe']
        assert result.binary.name in ('demo-app.exe', 'demo-app')

    def test_pyembed_stamp_hit_skips_download(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        calls: list[str] = []
        _stub_steps(monkeypatch, project, calls)
        pyembed = project / 'src-tauri' / 'pyembed'
        pyembed.mkdir()
        (pyembed / '.pyshade-stamp').write_text(pyembed_stamp(cpython_triple()), encoding='utf-8')

        package_app('demo_app.app:app', project, out_dir=tmp_path / 'out', bundles=('nsis',), skip_bundle=True)
        assert not any(c.startswith('ensure') or c == 'extract' for c in calls)

    def test_fresh_pyembed_forces_rebuild(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        calls: list[str] = []
        _stub_steps(monkeypatch, project, calls)
        pyembed = project / 'src-tauri' / 'pyembed'
        pyembed.mkdir()
        (pyembed / '.pyshade-stamp').write_text(pyembed_stamp(cpython_triple()), encoding='utf-8')

        package_app(
            'demo_app.app:app',
            project,
            out_dir=tmp_path / 'out',
            bundles=('nsis',),
            skip_bundle=True,
            fresh_pyembed=True,
        )
        assert 'extract' in calls

    def test_preflight_failure_aggregated(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        project = _make_project(tmp_path)

        def failing_preflight(project_dir: Path) -> list[str]:
            return ['缺 A', '缺 B']

        monkeypatch.setattr(packager, 'preflight_issues', failing_preflight)
        with pytest.raises(TauriCliError) as excinfo:
            package_app('demo_app.app:app', project, out_dir=tmp_path / 'out', skip_bundle=True)
        assert '缺 A' in str(excinfo.value) and '缺 B' in str(excinfo.value)

    def test_skip_bundle_requires_existing_frontend(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        calls: list[str] = []
        _stub_steps(monkeypatch, project, calls)
        (project / 'src-tauri' / 'frontend' / 'index.html').unlink()
        with pytest.raises(TauriCliError, match='skip-bundle'):
            package_app('demo_app.app:app', project, out_dir=tmp_path / 'out', skip_bundle=True)

    def test_empty_bundle_output_rejected(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        calls: list[str] = []
        _stub_steps(monkeypatch, project, calls)

        def build_nothing(project_dir: Path, env: dict[str, Any], *, bundles: tuple[str, ...], profile: str) -> None:
            pass

        monkeypatch.setattr(packager, 'run_tauri_build', build_nothing)
        with pytest.raises(TauriCliError, match='未产出安装包'):
            package_app('demo_app.app:app', project, out_dir=tmp_path / 'out', bundles=('nsis',), skip_bundle=True)
