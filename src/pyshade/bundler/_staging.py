"""staging 树组装:_frontend 源码拷入工作目录(vendor 经 NODE_PATH 引用,不拷贝)。

M4 增量(design.md §3.6):staging 输入指纹与 `.staging-stamp` 一致时跳过 copytree——
wheel 安装下框架源码永不变(恒命中),editable 布局改框架源码即失效。
"""

import hashlib
import shutil
from pathlib import Path

from pyshade.bundler._assets import FrontendAssets

_SRC_PARTS = ('runtime', 'ipc', 'components', 'lib')

_STAMP_NAME = '.staging-stamp'


def staging_stamp(assets: FrontendAssets, parts: tuple[str, ...]) -> str:
    """staging 输入指纹:各 part 全部文件的 (相对路径, size, mtime_ns)。"""
    digest = hashlib.sha256()
    for part in parts:
        base = assets.src_dir / part
        digest.update(f'::part {part}\n'.encode())
        for path in sorted(base.rglob('*')):
            if not path.is_file():
                continue
            stat = path.stat()
            digest.update(f'{path.relative_to(base).as_posix()}|{stat.st_size}|{stat.st_mtime_ns}\n'.encode())
    return digest.hexdigest()


def prepare_staging(workdir: Path, assets: FrontendAssets, *, extra_parts: tuple[str, ...] = ()) -> str:
    """把前端运行时源码铺进 workdir/src(幂等),返回 staging 指纹;指纹命中即跳过拷贝。"""
    parts = (*_SRC_PARTS, *extra_parts)
    stamp = staging_stamp(assets, parts)
    marker = workdir / _STAMP_NAME
    src = workdir / 'src'
    if src.is_dir() and marker.is_file() and marker.read_text(encoding='utf-8') == stamp:
        return stamp

    for part in parts:
        target = src / part
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(assets.src_dir / part, target)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(stamp, encoding='utf-8', newline='\n')
    return stamp
