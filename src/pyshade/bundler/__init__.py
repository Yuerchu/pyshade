"""零 Node 打包管线(design.md §3.6):pyshade bundle 的编排入口。

用户环境只有 Python + pip:esbuild 官方二进制(下载缓存)、wheel 内 _frontend 源码与
物化 vendor(NODE_PATH 解析)、预编译 style.css。产物 dist/ 即 pytauri frontendDist。

M4 窄版增量:staging 指纹跳 copytree + esbuild 输入内容哈希跳全量构建(`.bundle-stamp.json`,
成功后才写,崩溃安全);`PYSHADE_BUNDLE_FRESH=1` 逃生。index.html/style.css 每次照常重写
(theme/scheme/dev-client 注入不受跳过影响,幂等且廉价)。
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger as l

from pyshade.app import ShadeApp
from pyshade.bundler._assets import FrontendAssets, locate_assets
from pyshade.bundler._entry import emit_entry_tsx, emit_tsconfig
from pyshade.bundler._esbuild import ESBUILD_VERSION, ensure_esbuild, run_esbuild
from pyshade.bundler._html import write_static
from pyshade.bundler._staging import prepare_staging
from pyshade.compiler import compile_app

__all__ = ['BundleResult', 'bundle_app', 'bundle_testkit']

_BUNDLE_STAMP = '.bundle-stamp.json'


@dataclass(frozen=True, slots=True)
class BundleResult:
    out_dir: Path
    app_js_bytes: int
    duration_ms: float
    staging_ms: float = 0.0
    compile_ms: float = 0.0
    esbuild_ms: float = 0.0
    esbuild_skipped: bool = False


def esbuild_args(*, entry: str, outfile: Path, dev: bool) -> list[str]:
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
    return args


def _esbuild_input_hash(
    work: Path,
    *,
    staging_stamp: str,
    args: list[str],
    node_path: str,
    vendor_stamp: Path,
    esbuild: Path,
) -> str:
    """esbuild 输入指纹:staged 源码指纹 + generated/entry/tsconfig 全部内容 + 版本与参数 +
    vendor 指纹源内容 + 实际二进制身份。

    漏项即错误跳过——输入面全列;theme.gen.css 在 generated 目录内,天然入哈希。
    vendor 指纹按 manifest/lockfile 内容(npm 包版本不可变,O(1) 且免 mtime 漂移假重建);
    二进制身份盖住 PYSHADE_ESBUILD_PATH 覆盖换版本的情况(常量 ESBUILD_VERSION 感知不到)。
    """
    digest = hashlib.sha256()
    digest.update(f'esbuild {ESBUILD_VERSION}\n'.encode())
    bin_stat = esbuild.stat()
    digest.update(f'esbuild_bin {esbuild}|{bin_stat.st_size}|{bin_stat.st_mtime_ns}\n'.encode())
    digest.update(('args ' + ' '.join(args) + '\n').encode())
    digest.update(f'staging {staging_stamp}\n'.encode())
    digest.update(f'node_path {node_path}\n'.encode())
    digest.update(b'::vendor-stamp\n')
    digest.update(vendor_stamp.read_bytes())
    for rel in ('src/entry.tsx', 'tsconfig.json'):
        digest.update(f'::{rel}\n'.encode())
        digest.update((work / rel).read_bytes())
    generated = work / 'src' / 'generated'
    for path in sorted(generated.rglob('*')):
        if path.is_file():
            digest.update(f'::{path.relative_to(generated).as_posix()}\n'.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def bundle_app(
    app: ShadeApp,
    out_dir: str | Path,
    *,
    dev: bool = False,
    workdir: str | Path = '.pyshade/build',
) -> BundleResult:
    """编译 + staging + esbuild,产出 index.html / app.js / style.css 三件套。"""
    started = time.monotonic()
    out = Path(out_dir).absolute()
    work = Path(workdir).absolute()
    assets: FrontendAssets = locate_assets()
    fresh_forced = os.environ.get('PYSHADE_BUNDLE_FRESH') == '1'

    staging_fingerprint = prepare_staging(work, assets, fresh=fresh_forced)
    t_staged = time.monotonic()
    compile_app(app, work / 'src' / 'generated')
    (work / 'src' / 'entry.tsx').write_text(emit_entry_tsx(app), encoding='utf-8', newline='\n')
    (work / 'tsconfig.json').write_text(emit_tsconfig(), encoding='utf-8', newline='\n')
    t_compiled = time.monotonic()

    esbuild = ensure_esbuild()
    out.mkdir(parents=True, exist_ok=True)
    outfile = out / 'app.js'
    args = esbuild_args(entry='src/entry.tsx', outfile=outfile, dev=dev)
    node_path = str(assets.node_modules)

    input_hash = _esbuild_input_hash(
        work,
        staging_stamp=staging_fingerprint,
        args=args,
        node_path=node_path,
        vendor_stamp=assets.vendor_stamp,
        esbuild=esbuild,
    )
    stamp_file = work / _BUNDLE_STAMP
    skipped = False
    if not fresh_forced and outfile.is_file() and stamp_file.is_file():
        try:
            recorded: object = json.loads(stamp_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            recorded = None
        # stamp 同时记产物 size:app.js 被外部截断/损坏时不得静默复用
        skipped = recorded == {'hash': input_hash, 'size': outfile.stat().st_size}
    if not skipped:
        env = {**os.environ, 'NODE_PATH': node_path}
        run_esbuild(esbuild, args, cwd=work, env=env)
        stamp_file.write_text(
            json.dumps({'hash': input_hash, 'size': outfile.stat().st_size}), encoding='utf-8', newline='\n'
        )
    t_bundled = time.monotonic()

    theme_css: str | None = None
    if app.theme is not None:
        from pyshade.compiler.emit_theme import emit_theme_css

        theme_css = emit_theme_css(app.theme)
    write_static(out, assets, theme_css=theme_css, color_scheme=app.color_scheme)

    duration = (time.monotonic() - started) * 1000
    size = outfile.stat().st_size
    result = BundleResult(
        out_dir=out,
        app_js_bytes=size,
        duration_ms=duration,
        staging_ms=(t_staged - started) * 1000,
        compile_ms=(t_compiled - t_staged) * 1000,
        esbuild_ms=(t_bundled - t_compiled) * 1000,
        esbuild_skipped=skipped,
    )
    l.info(
        "pyshade bundle: {} ({:.0f} KB, {:.0f} ms = staging {:.0f} / compile {:.0f} / esbuild {:.0f}{})",
        out,
        size / 1024,
        duration,
        result.staging_ms,
        result.compile_ms,
        result.esbuild_ms,
        ' [skipped]' if skipped else '',
    )
    return result


def bundle_testkit(out_file: str | Path, *, workdir: str | Path = '.pyshade/testkit-build') -> Path:
    """testkit 的 esbuild 构建(IIFE 单文件):CI 用来对照 vite 产物行为一致性。

    仅仓库布局可用(testkit 不进 wheel)。
    """
    out = Path(out_file).absolute()
    work = Path(workdir).absolute()
    assets = locate_assets()
    if not (assets.src_dir / 'testkit').is_dir():
        raise RuntimeError("testkit 源码不存在:bundle_testkit 仅支持仓库布局")

    prepare_staging(work, assets, extra_parts=('testkit',), fresh=os.environ.get('PYSHADE_BUNDLE_FRESH') == '1')
    (work / 'tsconfig.json').write_text(emit_tsconfig(), encoding='utf-8', newline='\n')

    esbuild = ensure_esbuild()
    out.parent.mkdir(parents=True, exist_ok=True)
    args = [
        'src/testkit/index.ts',
        '--bundle',
        '--format=iife',
        f'--outfile={out}',
        '--tsconfig=tsconfig.json',
        '--jsx=automatic',
        '--define:process.env.NODE_ENV="production"',
        '--target=es2020',
    ]
    env = {**os.environ, 'NODE_PATH': str(assets.node_modules)}
    run_esbuild(esbuild, args, cwd=work, env=env)
    l.info("pyshade bundle-testkit: {} ({:.0f} KB)", out, out.stat().st_size / 1024)
    return out
