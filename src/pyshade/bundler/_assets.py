"""前端资产定位:wheel 包数据优先,仓库布局回退(editable install / dogfooding)。"""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path


class AssetsNotFoundError(RuntimeError):
    """找不到前端资产:wheel 缺件或仓库布局不完整。"""


@dataclass(frozen=True, slots=True)
class FrontendAssets:
    src_dir: Path
    """frontend 运行时源码根(含 runtime/ipc/components/lib)。"""
    node_modules: Path
    """vendor 依赖树(经 NODE_PATH 供 esbuild 解析,不拷贝)。"""
    style_css: Path
    """预编译 Tailwind 产物。"""
    index_html: Path
    """bundle 模板 index.html。"""
    vendor_stamp: Path
    """vendor 依赖树的内容指纹源(wheel=vendor-manifest.json / 仓库=pnpm-lock.yaml):
    依赖升级必须打掉 esbuild 输入哈希,否则错跳构建输出陈旧 app.js。"""


def _package_assets() -> FrontendAssets | None:
    root = resources.files('pyshade') / '_frontend'
    try:
        src = Path(str(root / 'src'))
    except TypeError:  # zip 安装等不可映射为路径的形态
        return None
    if not src.is_dir():
        return None
    base = src.parent
    return FrontendAssets(
        src_dir=src,
        node_modules=base / 'vendor' / 'node_modules',
        style_css=base / 'static' / 'style.css',
        index_html=base / 'static' / 'index.html',
        vendor_stamp=base / 'vendor-manifest.json',
    )


def _repo_assets() -> FrontendAssets | None:
    repo = Path(__file__).resolve().parents[3]
    frontend = repo / 'frontend'
    if not (frontend / 'src' / 'runtime').is_dir():
        return None
    return FrontendAssets(
        src_dir=frontend / 'src',
        node_modules=frontend / 'node_modules',
        style_css=frontend / 'dist-style' / 'style.css',
        index_html=frontend / 'bundle' / 'index.html',
        vendor_stamp=frontend / 'pnpm-lock.yaml',
    )


def locate_assets() -> FrontendAssets:
    assets = _package_assets() or _repo_assets()
    if assets is None:
        raise AssetsNotFoundError(
            "找不到 pyshade 前端资产:wheel 安装应包含 pyshade/_frontend;仓库内开发需存在 frontend/src/runtime"
        )
    missing: list[str] = []
    if not assets.node_modules.is_dir():
        missing.append(f"vendor 依赖树 {assets.node_modules}(仓库内:pnpm -C frontend install)")
    if not assets.style_css.is_file():
        missing.append(f"预编译样式 {assets.style_css}(仓库内:pnpm -C frontend build:css)")
    if not assets.index_html.is_file():
        missing.append(f"index.html 模板 {assets.index_html}")
    if not assets.vendor_stamp.is_file():
        missing.append(f"vendor 指纹源 {assets.vendor_stamp}(wheel:vendor-manifest.json / 仓库:pnpm-lock.yaml)")
    if missing:
        raise AssetsNotFoundError("前端资产缺件:\n  - " + "\n  - ".join(missing))
    return assets
