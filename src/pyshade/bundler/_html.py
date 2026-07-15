"""静态产物落盘:index.html 模板 + 预编译 style.css 拷入输出目录。

theme_css 非 None 时在 style.css link 之后内联 `<style data-pyshade-theme>`
(dist 保持三件套契约,:root 同 specificity 后到者胜);None 时字节级不变。
"""

import shutil
from pathlib import Path

from pyshade.bundler._assets import FrontendAssets

_STYLE_LINK = '<link rel="stylesheet" href="./style.css" />'


def inject_theme_style(html: str, theme_css: str) -> str:
    block = f'<style data-pyshade-theme>\n{theme_css.rstrip()}\n    </style>'
    if _STYLE_LINK in html:
        return html.replace(_STYLE_LINK, f'{_STYLE_LINK}\n    {block}', 1)
    return html.replace('</head>', f'  {block}\n  </head>', 1)


def write_static(out_dir: Path, assets: FrontendAssets, *, theme_css: str | None = None) -> None:
    if theme_css is None:
        shutil.copy2(assets.index_html, out_dir / 'index.html')
    else:
        html = assets.index_html.read_text(encoding='utf-8')
        (out_dir / 'index.html').write_text(inject_theme_style(html, theme_css), encoding='utf-8', newline='\n')
    shutil.copy2(assets.style_css, out_dir / 'style.css')
