"""零 Node 打包管线(design.md §3.6):pyshade bundle 的编排入口。

用户环境只有 Python + pip:esbuild 官方二进制(下载缓存)、wheel 内 _frontend 源码与
物化 vendor(NODE_PATH 解析)、预编译 style.css。产物 dist/ 即 pytauri frontendDist。
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger as l

from pyshade.app import ShadeApp
from pyshade.bundler._assets import FrontendAssets, locate_assets
from pyshade.bundler._entry import emit_entry_tsx, emit_tsconfig
from pyshade.bundler._esbuild import ensure_esbuild, run_esbuild
from pyshade.bundler._html import write_static
from pyshade.bundler._staging import prepare_staging
from pyshade.compiler import compile_app

__all__ = ['BundleResult', 'bundle_app', 'bundle_testkit']


@dataclass(frozen=True, slots=True)
class BundleResult:
    out_dir: Path
    app_js_bytes: int
    duration_ms: float


def esbuild_args(*, entry: str, outfile: Path, dev: bool, watch: bool) -> list[str]:
    """组装 esbuild CLI 参数(独立函数便于单测断言,不联网不起进程)。"""
    node_env = 'development' if dev else 'production'
    args = [
        entry,
        '--bundle',
        '--format=esm',
        f'--outfile={outfile}',
        '--tsconfig=tsconfig.json',
        '--jsx=automatic',
        f'--define:process.env.NODE_ENV="{node_env}"',
        '--target=es2020',
    ]
    if dev:
        args.append('--sourcemap')
    else:
        args.append('--minify')
    if watch:
        args.append('--watch=forever')
    return args


def bundle_app(
    app: ShadeApp,
    out_dir: str | Path,
    *,
    dev: bool = False,
    watch: bool = False,
    workdir: str | Path = '.pyshade/build',
) -> BundleResult:
    """编译 + staging + esbuild,产出 index.html / app.js / style.css 三件套。"""
    started = time.monotonic()
    out = Path(out_dir).absolute()
    work = Path(workdir).absolute()
    assets: FrontendAssets = locate_assets()

    prepare_staging(work, assets)
    compile_app(app, work / 'src' / 'generated')
    (work / 'src' / 'entry.tsx').write_text(emit_entry_tsx(app), encoding='utf-8', newline='\n')
    (work / 'tsconfig.json').write_text(emit_tsconfig(), encoding='utf-8', newline='\n')

    esbuild = ensure_esbuild()
    out.mkdir(parents=True, exist_ok=True)
    args = esbuild_args(entry='src/entry.tsx', outfile=out / 'app.js', dev=dev, watch=watch)
    env = {**os.environ, 'NODE_PATH': str(assets.node_modules)}
    run_esbuild(esbuild, args, cwd=work, env=env)

    write_static(out, assets)

    duration = (time.monotonic() - started) * 1000
    size = (out / 'app.js').stat().st_size
    l.info("pyshade bundle: {} ({:.0f} KB, {:.0f} ms)", out, size / 1024, duration)
    return BundleResult(out_dir=out, app_js_bytes=size, duration_ms=duration)


def bundle_testkit(out_file: str | Path, *, workdir: str | Path = '.pyshade/testkit-build') -> Path:
    """testkit 的 esbuild 构建(IIFE 单文件):CI 用来对照 vite 产物行为一致性。

    仅仓库布局可用(testkit 不进 wheel)。
    """
    out = Path(out_file).absolute()
    work = Path(workdir).absolute()
    assets = locate_assets()
    if not (assets.src_dir / 'testkit').is_dir():
        raise RuntimeError("testkit 源码不存在:bundle_testkit 仅支持仓库布局")

    prepare_staging(work, assets, extra_parts=('testkit',))
    (work / 'tsconfig.json').write_text(emit_tsconfig(), encoding='utf-8', newline='\n')

    esbuild = ensure_esbuild()
    out.parent.mkdir(parents=True, exist_ok=True)
    args = [
        'src/testkit/index.ts',
        '--bundle',
        '--format=iife',
        f'--outfile={out}',
        '--tsconfig=tsconfig.json',
        '--target=es2020',
    ]
    env = {**os.environ, 'NODE_PATH': str(assets.node_modules)}
    run_esbuild(esbuild, args, cwd=work, env=env)
    l.info("pyshade bundle-testkit: {} ({:.0f} KB)", out, out.stat().st_size / 1024)
    return out
