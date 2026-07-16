"""内容渲染(M4,design.md §3.13):markdown 与代码高亮都发生在编译期。

- mistune `escape=True` 一律拒绝 raw HTML(即使内容是构建期作者可控,也不留口子);
- pygments `HtmlFormatter(nowrap=True)` 产出短 class(k/s1/c1…),样式经 `.shade-hl`
  后代选择器作用域化(frontend/src/index.css 手写块);
- 依赖挂 `pyshade[content]` extra,惰性 import,缺失即 CompileError 带安装提示;
- 本模块在 compiler 包内:emitter 字符串里的 class 被 index.css 的 @source 扫描命中。
"""

from typing import Any

from pyshade.compiler.errors import CompileError

_INSTALL_HINT = "Markdown/CodeBlock 组件需要编译期依赖:pip install 'pyshade[content]'(mistune + pygments)"


def highlight_code(code: str, language: str) -> str:
    """pygments 高亮为带短 class 的 span 串(nowrap:外层 <pre><code> 由 emitter 控制)。"""
    try:
        from pygments import highlight
        from pygments.formatters.html import HtmlFormatter
        from pygments.lexers import get_lexer_by_name  # pyright: ignore[reportUnknownVariableType]
        from pygments.util import ClassNotFound
    except ImportError as exc:
        raise CompileError(_INSTALL_HINT) from exc

    try:
        lexer = get_lexer_by_name(language)
    except ClassNotFound as exc:
        raise CompileError(
            f"CodeBlock: 未知语言 {language!r}(pygments 无对应 lexer)→ 请改用有效语言名或 'text'"
        ) from exc
    formatter: HtmlFormatter[str] = HtmlFormatter(nowrap=True)
    rendered: str = highlight(code, lexer, formatter)
    return rendered.rstrip('\n')


def render_markdown(source: str) -> str:
    """markdown → 静态 HTML(编译期):table/strikethrough/task_lists 插件,代码块走 pygments。"""
    try:
        import mistune
    except ImportError as exc:
        raise CompileError(_INSTALL_HINT) from exc

    class _ShadeRenderer(mistune.HTMLRenderer):
        def block_code(self, code: str, info: str | None = None) -> str:
            language = (info or '').strip().split(' ')[0] or 'text'
            return f'<pre class="shade-hl"><code>{highlight_code(code, language)}</code></pre>\n'

    markdown: Any = mistune.create_markdown(
        renderer=_ShadeRenderer(escape=True),
        plugins=['table', 'strikethrough', 'task_lists'],
    )
    html = markdown(source)
    assert isinstance(html, str)  # create_markdown 无 AST renderer 时恒为 str
    return html
