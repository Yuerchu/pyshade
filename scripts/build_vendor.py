"""发版工具:物化 vendor 依赖树到 frontend/dist-vendor(随 wheel 分发)。

npm --omit=dev --ignore-scripts --install-strategy=hoisted 产出真实文件树
(pnpm symlink 不能进 wheel),prune 文档类文件(保留 LICENSE),
并强校验版本与 frontend/pnpm-lock.yaml 一致。仅在框架仓库运行(需要 npm)。
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
FRONTEND = REPO / 'frontend'
VENDOR = FRONTEND / 'dist-vendor'

_PRUNE_PATTERNS = ('*.md', '*.markdown', '*.map', '*.flow', '*.ts.map')
_PRUNE_DIRS = ('.bin', 'profiling')


def materialize() -> None:
    if VENDOR.exists():
        shutil.rmtree(VENDOR)
    VENDOR.mkdir(parents=True)

    pkg = json.loads((FRONTEND / 'package.json').read_text(encoding='utf-8'))
    deps: dict[str, str] = dict(pkg['dependencies'])
    (VENDOR / 'package.json').write_text(
        json.dumps({'name': 'pyshade-vendor', 'private': True, 'dependencies': deps}, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    npm = shutil.which('npm')
    if npm is None:
        raise SystemExit("需要 npm(仅框架仓库发版使用)")
    result = subprocess.run(
        [npm, 'install', '--omit=dev', '--ignore-scripts', '--install-strategy=hoisted', '--no-audit', '--no-fund'],
        capture_output=True,
        encoding='utf-8',
        errors='replace',
        cwd=VENDOR,
        timeout=900,
    )
    if result.returncode != 0:
        raise SystemExit(f"npm install 失败:\n{(result.stderr or '')[-2000:]}")

    symlinks = [p for p in (VENDOR / 'node_modules').rglob('*') if p.is_symlink()]
    if symlinks:
        raise SystemExit(f"vendor 树含 symlink({len(symlinks)} 个),不能进 wheel")


def prune() -> None:
    node_modules = VENDOR / 'node_modules'
    removed = 0
    for pattern in _PRUNE_PATTERNS:
        for path in node_modules.rglob(pattern):
            if path.name.upper().startswith('LICENSE'):
                continue
            path.unlink()
            removed += 1
    for name in _PRUNE_DIRS:
        for path in node_modules.rglob(name):
            if path.is_dir():
                shutil.rmtree(path)
                removed += 1
    print(f"prune 移除 {removed} 项")


def verify_against_lock() -> None:
    """物化树的每个直接依赖版本必须能在 pnpm-lock.yaml 中找到(防两条管线漂移)。"""
    lock_text = (FRONTEND / 'pnpm-lock.yaml').read_text(encoding='utf-8')
    manifest: dict[str, str] = {}
    pkg = json.loads((FRONTEND / 'package.json').read_text(encoding='utf-8'))
    for name in pkg['dependencies']:
        installed = json.loads(
            (VENDOR / 'node_modules' / Path(*name.split('/')) / 'package.json').read_text(encoding='utf-8')
        )
        version = str(installed['version'])
        manifest[name] = version
        if not re.search(rf'{re.escape(name)}@{re.escape(version)}', lock_text):
            raise SystemExit(f"vendor 与 pnpm-lock 漂移:{name}@{version} 不在 pnpm-lock.yaml 中;先 pnpm install 同步")
    (VENDOR / 'vendor-manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n'
    )
    print(f"vendor-manifest: {len(manifest)} 个直接依赖,与 pnpm-lock 一致")


def main() -> None:
    materialize()
    prune()
    verify_against_lock()
    size = sum(f.stat().st_size for f in VENDOR.rglob('*') if f.is_file())
    print(f"dist-vendor 完成,总大小 {size / 1024 / 1024:.1f} MB")


if __name__ == '__main__':
    sys.exit(main())
