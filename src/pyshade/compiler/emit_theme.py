"""theme.gen.css 发射:覆盖 :root 变量(双层变量机制下预编译 style.css 仍可运行时换肤)。"""

from pyshade.theme import Theme, theme_tokens


def emit_theme_css(theme: Theme) -> str:
    """只输出已设置的 token;将来 dark mode 追加 .dark{} 块,不破此接口。"""
    lines = ['/* 由 pyshade 编译器生成 — 请勿手改。 */', ':root {']
    for token, value in theme_tokens(theme).items():
        lines.append(f'  --{token}: {value};')
    lines.append('}')
    return '\n'.join(lines) + '\n'
