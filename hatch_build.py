"""hatchling 构建钩子:前端资产存在才注入 wheel(design.md §3.6)。

dist-vendor/dist-style 是发版产物(scripts/build_vendor.py + pnpm build:css),
fresh checkout / editable 安装时不存在——静态 force-include 会让 uv sync 直接失败。
发版 wheel 的完整性由 CI wheel-assets job 的必备条目断言兜底,此处缺件不静默放行到发布。
"""

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
        force_include: dict[str, str] = build_data.setdefault('force_include', {})
        for src, dst in _FRONTEND_INCLUDES.items():
            if (Path(self.root) / src).exists():
                force_include[src] = dst
