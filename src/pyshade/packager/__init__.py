"""standalone 打包链(design.md §3.12,M3):pyshade init / pyshade package 的编排层。

用户环境 = Python + Rust(零 Node):便携 CPython(python-build-standalone,下载缓存)
+ `pyshade bundle` 前端产物烤入二进制 + cargo-tauri 出安装包。
"""

import json
import os
import platform as _platform_mod
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger as l

from pyshade.packager._cpython import (
    CPYTHON_VERSION,
    PBS_RELEASE,
    CpythonAcquireError,
    cpython_triple,
    ensure_cpython_tarball,
    extract_pyembed,
    pyembed_python_path,
    pyembed_stamp,
    read_pyembed_stamp,
)
from pyshade.packager._platform import build_env, patch_macos_dylib
from pyshade.packager._pyembed import compile_bytecode, install_project, warn_if_wheel_polluted
from pyshade.packager._tauri_cli import TauriCliError, preflight_issues, run_tauri_build

__all__ = [
    'CPYTHON_VERSION',
    'PBS_RELEASE',
    'CpythonAcquireError',
    'PackageResult',
    'cpython_triple',
    'default_bundles',
    'ensure_cpython_tarball',
    'extract_pyembed',
    'package_app',
    'pyembed_python_path',
    'pyembed_stamp',
    'read_pyembed_stamp',
]

_BUNDLE_SUBDIRS = ('nsis', 'msi', 'dmg', 'macos', 'deb', 'rpm', 'appimage')


@dataclass(frozen=True, slots=True)
class PackageResult:
    artifacts: list[Path]
    binary: Path
    pyembed_python: Path
    duration_ms: float


def default_bundles(system: str) -> tuple[str, ...]:
    """平台默认安装包集;Linux 默认不出 AppImage(libpython 挪位 known-issue,tauri#11898)。"""
    if system == 'windows':
        return ('nsis', 'msi')
    if system == 'darwin':
        return ('dmg', 'app')
    return ('deb',)


def _read_product_name(src_tauri: Path) -> str:
    conf = json.loads((src_tauri / 'tauri.conf.json').read_text(encoding='utf-8'))
    return str(conf['productName'])


def _read_crate_name(src_tauri: Path) -> str:
    from pyshade.packager._scaffold import load_toml

    cargo: dict[str, Any] = load_toml(src_tauri / 'Cargo.toml')
    package: dict[str, Any] = cargo['package']
    return str(package['name'])


def _check_config_drift(project_dir: Path, src_tauri: Path, pkg_name_hint: str | None) -> None:
    """Tauri.toml(dev 真相)与 tauri.conf.json(打包真相)的 identifier/productName 漂移比对。"""
    from pyshade.packager._scaffold import detect_package, load_toml

    try:
        pkg_name = detect_package(project_dir, pkg_name_hint)
    except Exception:
        return
    dev_toml = project_dir / 'src' / pkg_name / 'Tauri.toml'
    if not dev_toml.is_file():
        return
    dev: dict[str, Any] = load_toml(dev_toml)
    conf = json.loads((src_tauri / 'tauri.conf.json').read_text(encoding='utf-8'))
    for key in ('productName', 'identifier'):
        dev_value, conf_value = dev.get(key), conf.get(key)
        if dev_value is not None and dev_value != conf_value:
            l.warning(
                "pyshade.packager: {} 漂移——Tauri.toml(dev)= {!r},tauri.conf.json(打包)= {!r};"
                "以打包侧为准,建议 pyshade init --force 重新同步",
                key,
                dev_value,
                conf_value,
            )


def collect_artifacts(bundle_root: Path, out_dir: Path) -> list[Path]:
    """收集 target/<profile>/bundle/ 下的安装包到 out_dir(.app 目录整棵拷)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    collected: list[Path] = []
    for subdir in _BUNDLE_SUBDIRS:
        source = bundle_root / subdir
        if not source.is_dir():
            continue
        for entry in sorted(source.iterdir()):
            dest = out_dir / entry.name
            if entry.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                # symlinks=True:macOS .app 的 Frameworks/Versions 符号链接结构必须保真——
                # 解引用会膨胀体积且 code signature 的 sealed resources 记录的是 symlink,
                # 拷贝件校验必失败;悬空链接在此模式下按链接原样复制,不抛 shutil.Error
                shutil.copytree(entry, dest, symlinks=True)
            else:
                shutil.copy2(entry, dest)
            collected.append(dest)
    return collected


def package_app(
    app_spec: str,
    project_dir: Path,
    *,
    out_dir: Path,
    bundles: tuple[str, ...] | None = None,
    profile: str = 'bundle-release',
    extra_requirements: tuple[str, ...] = (),
    package: str | None = None,
    skip_bundle: bool = False,
    fresh_pyembed: bool = False,
    python_version: str = CPYTHON_VERSION,
    pbs_release: str = PBS_RELEASE,
) -> PackageResult:
    """八步编排:体检 → bundle → CPython → 平台修补 → 装依赖 → 预编译 → tauri build → 收集。"""
    started = time.monotonic()
    project_dir = project_dir.absolute()
    src_tauri = project_dir / 'src-tauri'
    system = _platform_mod.system().lower()

    # ① 前置体检(缺项一次性汇总)
    issues = preflight_issues(project_dir)
    if issues:
        raise TauriCliError("打包前置条件不满足:\n" + '\n'.join(f'  - {issue}' for issue in issues))
    _check_config_drift(project_dir, src_tauri, package)

    # ② 前端产物烤入 src-tauri/frontend
    frontend = src_tauri / 'frontend'
    if skip_bundle:
        if not (frontend / 'index.html').is_file():
            raise TauriCliError(f"--skip-bundle 但 {frontend} 下没有 index.html;先运行 pyshade bundle 或去掉该参数")
    else:
        from pyshade.bundler import bundle_app
        from pyshade.cli import load_app

        src_dir = project_dir / 'src'
        if src_dir.is_dir() and str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        bundle_app(load_app(app_spec), frontend, workdir=project_dir / '.pyshade' / 'package-build')

    # ③ 便携 CPython(stamp 增量)
    pyembed_dir = src_tauri / 'pyembed'
    wanted_stamp = pyembed_stamp(cpython_triple(), version=python_version, release=pbs_release)
    if fresh_pyembed or read_pyembed_stamp(pyembed_dir) != wanted_stamp:
        tarball = ensure_cpython_tarball(version=python_version, release=pbs_release)
        extract_pyembed(tarball, pyembed_dir, version=python_version, release=pbs_release)
    else:
        l.info("pyshade.packager: pyembed 已就绪({}),跳过解压", wanted_stamp)
    pyembed_python = pyembed_python_path(pyembed_dir)

    # ④ macOS install_name 修补(幂等,每次跑)
    if system == 'darwin':
        patch_macos_dylib(pyembed_dir)

    # ⑤ 项目 + 依赖装进内嵌解释器
    from pyshade.packager._scaffold import read_pyproject

    dist_name, _version = read_pyproject(project_dir)
    install_project(pyembed_python, project_dir, dist_name=dist_name, extra_requirements=extra_requirements)
    warn_if_wheel_polluted(pyembed_python)

    # ⑥ 预编译 .pyc(canary 教训:运行期生成的 .pyc 卸载残留;预编译进 resources 被追踪)
    compile_bytecode(pyembed_python)

    # ⑦ tauri build
    resolved_bundles = bundles if bundles is not None else default_bundles(system)
    product_name = _read_product_name(src_tauri)
    env = build_env(
        dict(os.environ),
        system=system,
        pyembed_python=pyembed_python,
        pyembed_dir=pyembed_dir,
        product_name=product_name,
    )
    run_tauri_build(project_dir, env, bundles=resolved_bundles, profile=profile)

    # ⑧ 收集产物
    crate_name = _read_crate_name(src_tauri)
    binary = src_tauri / 'target' / profile / (f'{crate_name}.exe' if system == 'windows' else crate_name)
    artifacts = collect_artifacts(src_tauri / 'target' / profile / 'bundle', out_dir)
    if not artifacts:
        raise TauriCliError(f"tauri build 未产出安装包(target/{profile}/bundle 为空);核对 --bundles 与平台支持")

    duration = (time.monotonic() - started) * 1000
    for artifact in artifacts:
        size = _tree_size(artifact)
        l.info("pyshade.packager: 产物 {}({:.1f} MB)", artifact, size / 1024 / 1024)
    l.info("pyshade.packager: 完成({} 个产物,{:.0f} s)", len(artifacts), duration / 1000)
    return PackageResult(artifacts=artifacts, binary=binary, pyembed_python=pyembed_python, duration_ms=duration)


def _tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
