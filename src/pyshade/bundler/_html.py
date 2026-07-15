"""静态产物落盘:index.html 模板 + 预编译 style.css 拷入输出目录。"""

import shutil
from pathlib import Path

from pyshade.bundler._assets import FrontendAssets


def write_static(out_dir: Path, assets: FrontendAssets) -> None:
    shutil.copy2(assets.index_html, out_dir / 'index.html')
    shutil.copy2(assets.style_css, out_dir / 'style.css')
