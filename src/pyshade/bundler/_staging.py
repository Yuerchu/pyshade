"""staging 树组装:_frontend 源码拷入工作目录(vendor 经 NODE_PATH 引用,不拷贝)。"""

import shutil
from pathlib import Path

from pyshade.bundler._assets import FrontendAssets

_SRC_PARTS = ('runtime', 'ipc', 'components', 'lib')


def prepare_staging(workdir: Path, assets: FrontendAssets, *, extra_parts: tuple[str, ...] = ()) -> None:
    """把前端运行时源码铺进 workdir/src(全量覆盖,幂等);generated 由 compile_app 随后写入。"""
    src = workdir / 'src'
    for part in (*_SRC_PARTS, *extra_parts):
        target = src / part
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(assets.src_dir / part, target)
