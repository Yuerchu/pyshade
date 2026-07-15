"""pyshade init:参数推断、模板渲染产物、幂等/--force、错误分支(不联网)。"""

import json
from pathlib import Path

import pytest

from pyshade.packager._scaffold import ScaffoldError, infer_params, init_project

_TAURI_TOML = """
"$schema" = "https://schema.tauri.app/config/2"
productName = "my-demo-app"
version = "0.2.0"
identifier = "cn.example.demo"

[[app.windows]]
title = "Demo Window"
width = 480
height = 720
"""


def _make_project(tmp_path: Path, *, with_tauri_toml: bool = True) -> Path:
    project = tmp_path / 'demo'
    (project / 'src' / 'demo_app').mkdir(parents=True)
    (project / 'src' / 'demo_app' / '__init__.py').write_text('', encoding='utf-8')
    (project / 'pyproject.toml').write_text(
        '[project]\nname = "demo-app"\nversion = "0.2.0"\n',
        encoding='utf-8',
    )
    if with_tauri_toml:
        (project / 'src' / 'demo_app' / 'Tauri.toml').write_text(_TAURI_TOML, encoding='utf-8')
    return project


class TestInferParams:
    def test_full_inference_from_tauri_toml(self, tmp_path: Path) -> None:
        params = infer_params(_make_project(tmp_path))
        assert params.pkg_name == 'demo_app'
        assert params.crate_name == 'demo-app'
        assert params.lib_name == 'demo_app_lib'
        assert params.product_name == 'my-demo-app'
        assert params.identifier == 'cn.example.demo'
        assert params.version == '0.2.0'
        assert (params.window_title, params.window_width, params.window_height) == ('Demo Window', 480, 720)

    def test_defaults_without_tauri_toml(self, tmp_path: Path) -> None:
        params = infer_params(_make_project(tmp_path, with_tauri_toml=False))
        assert params.product_name == 'demo-app'
        assert params.identifier == 'com.example.demo-app'  # 占位 + warn
        assert (params.window_title, params.window_width, params.window_height) == ('demo-app', 800, 600)

    def test_cli_overrides_win(self, tmp_path: Path) -> None:
        params = infer_params(_make_project(tmp_path), product_name='Custom', identifier='io.custom.x')
        assert params.product_name == 'Custom'
        assert params.identifier == 'io.custom.x'

    def test_multiple_packages_require_explicit(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        (project / 'src' / 'other_pkg').mkdir()
        (project / 'src' / 'other_pkg' / '__init__.py').write_text('', encoding='utf-8')
        with pytest.raises(ScaffoldError, match='--package'):
            infer_params(project)
        assert infer_params(project, package='demo_app').pkg_name == 'demo_app'

    def test_missing_pyproject_rejected(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        (project / 'pyproject.toml').unlink()
        with pytest.raises(ScaffoldError, match='pyproject.toml'):
            infer_params(project)


class TestInitProject:
    def test_generates_expected_tree(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        result = init_project(project)
        rel = sorted(str(p.relative_to(result.src_tauri_dir)).replace('\\', '/') for p in result.created)
        assert rel == [
            '.gitignore',
            '.taurignore',
            'Cargo.toml',
            'build.rs',
            'capabilities/default.toml',
            'icons/icon.ico',
            'icons/icon.png',
            'src/lib.rs',
            'src/main.rs',
            'tauri.bundle.json',
            'tauri.conf.json',
        ]
        assert result.skipped == []

    def test_rendered_contents(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        src_tauri = init_project(project).src_tauri_dir

        cargo = (src_tauri / 'Cargo.toml').read_text(encoding='utf-8')
        assert 'name = "demo-app"' in cargo
        assert 'name = "demo_app_lib"' in cargo
        assert 'tauri-plugin-pytauri' in cargo  # canary 教训:必须直接依赖

        main_rs = (src_tauri / 'src' / 'main.rs').read_text(encoding='utf-8')
        assert 'use demo_app_lib::{ext_mod, tauri_generate_context};' in main_rs
        assert 'PythonScript::Module("demo_app".into())' in main_rs

        conf = json.loads((src_tauri / 'tauri.conf.json').read_text(encoding='utf-8'))
        assert conf['productName'] == 'my-demo-app'
        assert conf['identifier'] == 'cn.example.demo'
        assert conf['build']['frontendDist'] == './frontend'
        assert conf['build']['features'] == ['pytauri/standalone']
        assert conf['app']['windows'][0] == {'title': 'Demo Window', 'width': 480, 'height': 720}

        bundle = json.loads((src_tauri / 'tauri.bundle.json').read_text(encoding='utf-8'))
        assert bundle['bundle']['resources'] == {'pyembed/python': './'}

    def test_idempotent_skip_and_force(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        init_project(project)
        marker = project / 'src-tauri' / 'Cargo.toml'
        marker.write_text('# user edited\n', encoding='utf-8')

        second = init_project(project)
        assert second.created == []
        assert len(second.skipped) == 11
        assert marker.read_text(encoding='utf-8') == '# user edited\n'  # 不覆盖

        forced = init_project(project, force=True)
        assert len(forced.created) == 11
        assert 'name = "demo-app"' in marker.read_text(encoding='utf-8')
