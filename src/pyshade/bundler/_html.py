"""静态产物落盘:index.html 模板 + 预编译 style.css 拷入输出目录。

- 配色 boot script 恒注入(M4 dark mode):head 内联同步脚本在首帧前挂 .dark class,
  防白闪(app.js 是 module,首帧可能先于其执行);默认值 = ShadeApp.color_scheme,
  localStorage 显式选择优先——与 runtime Provider 的解析规则一致。
- theme_css 非 None 时在 style.css link 之后内联 `<style data-pyshade-theme>`
  (dist 保持三件套契约,后到者按 CSS 层叠规则覆盖)。
"""

import shutil
from pathlib import Path

from pyshade.bundler._assets import FrontendAssets

_STYLE_LINK = '<link rel="stylesheet" href="./style.css" />'

_DEFAULT_DARK_JS = {
    'system': 's !== "light" && (s === "dark" || matchMedia("(prefers-color-scheme: dark)").matches)',
    'light': 's === "dark"',
    'dark': 's !== "light"',
}


def scheme_boot_script(color_scheme: str) -> str:
    """首帧前的配色解析(与 runtime scheme.ts 同规则):localStorage 显式选择 ?? app 默认。"""
    resolve = _DEFAULT_DARK_JS[color_scheme]
    return (
        '<script data-pyshade-scheme>\n'
        '      (() => { try {\n'
        '        const s = localStorage.getItem("pyshade:color-scheme");\n'
        f'        document.documentElement.classList.toggle("dark", {resolve});\n'
        '      } catch (e) { /* localStorage 不可用时保持亮色 */ } })();\n'
        '    </script>'
    )


def inject_scheme_boot(html: str, color_scheme: str) -> str:
    block = scheme_boot_script(color_scheme)
    if _STYLE_LINK in html:
        return html.replace(_STYLE_LINK, f'{block}\n    {_STYLE_LINK}', 1)
    return html.replace('</head>', f'  {block}\n  </head>', 1)


def inject_theme_style(html: str, theme_css: str) -> str:
    block = f'<style data-pyshade-theme>\n{theme_css.rstrip()}\n    </style>'
    if _STYLE_LINK in html:
        return html.replace(_STYLE_LINK, f'{_STYLE_LINK}\n    {block}', 1)
    return html.replace('</head>', f'  {block}\n  </head>', 1)


def write_static(
    out_dir: Path,
    assets: FrontendAssets,
    *,
    theme_css: str | None = None,
    color_scheme: str = 'system',
) -> None:
    html = assets.index_html.read_text(encoding='utf-8')
    html = inject_scheme_boot(html, color_scheme)
    if theme_css is not None:
        html = inject_theme_style(html, theme_css)
    (out_dir / 'index.html').write_text(html, encoding='utf-8', newline='\n')
    shutil.copy2(assets.style_css, out_dir / 'style.css')
