"""hatchling 构建钩子:前端资产存在才注入 wheel(design.md §3.6)。

dist-vendor/dist-style 是发版产物(scripts/build_vendor.py + pnpm build:css),
fresh checkout / editable 安装时不存在——静态 force-include 会让 uv sync 直接失败。
发版路径设 `PYSHADE_REQUIRE_FRONTEND_ASSETS=1`(ci/release 的 wheel-assets job):
缺任一资产直接构建失败,不再只靠事后 zip 断言;本地开发不设,行为不变。
"""

import os
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_FRONTEND_INCLUDES: dict[str, str] = {
    'frontend/src/runtime': 'pyshade/_frontend/src/runtime',
    'frontend/src/ipc': 'pyshade/_frontend/src/ipc',
    'frontend/src/components': 'pyshade/_frontend/src/components',
    'frontend/src/lib': 'pyshade/_frontend/src/lib',
    'frontend/bundle/index.html': 'pyshade/_frontend/static/index.html',
    'frontend/dist-style/style.css': 'pyshade/_frontend/static/style.css',
    'frontend/dist-vendor/node_modules': 'pyshade/_frontend/vendor/node_modules',
    'frontend/dist-vendor/vendor-manifest.json': 'pyshade/_frontend/vendor-manifest.json',
}


class FrontendAssetsHook(BuildHookInterface):  # pyright: ignore[reportMissingTypeArgument, reportUntypedBaseClass]
    PLUGIN_NAME = 'custom'

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if version == 'editable':
            # editable 布局下 resources.files('pyshade') 指向 src/pyshade,注入产物会被物理拷进
            # site-packages 却永不被 _package_assets 读取(运行时走仓库回退)——9.4MB 纯死重
            return
        strict = os.environ.get('PYSHADE_REQUIRE_FRONTEND_ASSETS') == '1'
        force_include: dict[str, str] = build_data.setdefault('force_include', {})
        missing: list[str] = []
        for src, dst in _FRONTEND_INCLUDES.items():
            if (Path(self.root) / src).exists():
                force_include[src] = dst
            else:
                missing.append(src)
        if strict and missing:
            raise RuntimeError(
                f"发版 wheel 缺前端资产:{', '.join(missing)};"
                "先 pnpm -C frontend build:css 且 uv run python scripts/build_vendor.py"
            )
