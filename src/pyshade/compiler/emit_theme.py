"""theme.gen.css 发射:覆盖 :root/.dark 变量(双层变量机制下预编译 style.css 仍可运行时换肤)。

三段按需发射(M4 dark mode):
- `:root`:模式无关 token(radius);
- `:root:not(.dark)`:亮色颜色 token——`:not` 把 specificity 提到 (0,2,0),
  保证内联 <style> 后到也不会压过 style.css 里内置的 .dark 暗色默认值;
- `.dark`:theme.dark 的暗色 token。
"""

from pyshade.theme import MODE_INDEPENDENT_TOKENS, Theme, theme_tokens

_MODE_INDEPENDENT_KEBAB = frozenset(name.replace('_', '-') for name in MODE_INDEPENDENT_TOKENS)


def _block(selector: str, tokens: dict[str, str]) -> list[str]:
    lines = [f'{selector} {{']
    for token, value in tokens.items():
        lines.append(f'  --{token}: {value};')
    lines.append('}')
    return lines


def emit_theme_css(theme: Theme) -> str:
    """只输出已设置的 token;无内容的段不发射。"""
    light = theme_tokens(theme)
    shared = {k: v for k, v in light.items() if k in _MODE_INDEPENDENT_KEBAB}
    light_only = {k: v for k, v in light.items() if k not in _MODE_INDEPENDENT_KEBAB}
    dark = theme_tokens(theme.dark) if theme.dark is not None else {}

    lines = ['/* 由 pyshade 编译器生成 — 请勿手改。 */']
    if shared:
        lines.extend(_block(':root', shared))
    if light_only:
        lines.extend(_block(':root:not(.dark)', light_only))
    if dark:
        lines.extend(_block('.dark', dark))
    return '\n'.join(lines) + '\n'
