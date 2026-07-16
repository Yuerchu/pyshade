"""静态导出的纯函数面(build.py 编排消费,tests/docs_site 直接测):

- md 快照:与 HTML 页同源同数据(introspect + 翻译表 + demo 源码),不漂移;
- llms.txt:链接一律指 .md 快照——hash SPA 对 LLM 抓取是空 index.html(定案);
- 根跳转 index.html(navigator.language)与 demo-mock 注入。
"""

import inspect

from docs_site.content import en_summaries, guide_md
from docs_site.demos import DEMOS
from docs_site.i18n import Locale, t
from docs_site.pages import props_table_md
from pyshade.docs import ComponentDoc

_GUIDES = ('home', 'quickstart')


def component_md(doc: ComponentDoc, locale: Locale) -> str:
    """单组件的 markdown 快照:摘要 + props 表 + demo 源码。"""
    summary = doc.docstring if locale == 'zh' else en_summaries()[doc.class_name]
    source = inspect.getsource(DEMOS[doc.tag])
    lines = [
        f'# {doc.tag}',
        '',
        summary,
        '',
        f"## {t('props_heading', locale)}",
        '',
        props_table_md(doc, locale),
        '',
        f"## {t('demo_source', locale)}",
        '',
        '```python',
        source.rstrip('\n'),
        '```',
        '',
    ]
    return '\n'.join(lines)


def md_snapshots(docs: list[ComponentDoc], locale: Locale) -> dict[str, str]:
    """相对路径(不含 locale 前缀)→ markdown 文本。"""
    out: dict[str, str] = {}
    for slug in _GUIDES:
        out[f'md/guides/{slug}.md'] = guide_md(slug, locale)
    for doc in docs:
        out[f'md/components/{doc.tag}.md'] = component_md(doc, locale)
    return out


def _locale_prefix(base_url: str, locale: Locale) -> str:
    return f"{base_url.rstrip('/')}/{locale}"


def llms_txt(docs: list[ComponentDoc], *, base_url: str, locale: Locale) -> str:
    """llmstxt.org 形态:H1 + blockquote + H2 链接组,链接指 md 快照。"""
    prefix = _locale_prefix(base_url, locale)
    lines = [
        '# PyShade',
        '',
        f"> {t('tagline', locale)}",
        '',
        f"## {t('nav_quickstart', locale)}",
        '',
        f"- [{t('nav_home', locale)}]({prefix}/md/guides/home.md)",
        f"- [{t('nav_quickstart', locale)}]({prefix}/md/guides/quickstart.md)",
        '',
        f"## {t('nav_components', locale)}",
        '',
    ]
    for doc in docs:
        lines.append(f'- [{doc.tag}]({prefix}/md/components/{doc.tag}.md)')
    lines.extend(
        [
            '',
            '## Optional',
            '',
            '- [Design document (zh-CN)](https://github.com/Yuerchu/pyshade/blob/main/docs/design.md)',
            '- [Source repository](https://github.com/Yuerchu/pyshade)',
            '',
        ]
    )
    return '\n'.join(lines)


def llms_full_txt(docs: list[ComponentDoc], locale: Locale) -> str:
    """全文拼接(guides + 全组件快照),单文件喂给长上下文 LLM。"""
    parts = [f'# PyShade — full documentation ({locale})', '']
    for slug in _GUIDES:
        parts.extend([guide_md(slug, locale), '', '---', ''])
    for doc in docs:
        parts.extend([component_md(doc, locale), '---', ''])
    return '\n'.join(parts)


def redirect_html(*, default: Locale = 'en') -> str:
    """根 index.html:navigator.language 跳 /en/ 或 /zh/,含 hreflang alternate。"""
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>PyShade Docs</title>
    <link rel="alternate" hreflang="en" href="./en/" />
    <link rel="alternate" hreflang="zh" href="./zh/" />
    <script>
      const zh = (navigator.language || "").toLowerCase().startsWith("zh");
      location.replace(zh ? "./zh/" : "./{default}/");
    </script>
  </head>
  <body>
    <noscript><a href="./{default}/">PyShade Docs</a></noscript>
  </body>
</html>
"""


def inject_mock_script(html: str) -> str:
    """demo-mock.js 注入 app.js 之前(mock 先就位再加载运行时);幂等。"""
    tag = '<script src="./demo-mock.js"></script>'
    if 'demo-mock.js' in html:
        return html
    app_tag = '<script type="module" src="./app.js"></script>'
    if app_tag in html:
        return html.replace(app_tag, f'{tag}\n    {app_tag}', 1)
    return html.replace('</head>', f'  {tag}\n  </head>', 1)
