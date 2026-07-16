"""静态导出纯函数:md 快照同源、llms.txt 格式与链接对账、mock 注入、根跳转。"""

import re

from docs_site.export import component_md, inject_mock_script, llms_full_txt, llms_txt, md_snapshots, redirect_html

from pyshade.docs import collect_components

DOCS = collect_components()
BASE = 'https://docs.example.test'


class TestSnapshots:
    def test_snapshot_paths_cover_guides_and_components(self) -> None:
        snapshots = md_snapshots(DOCS, 'en')
        assert 'md/guides/quickstart.md' in snapshots
        assert 'md/guides/home.md' in snapshots
        for doc in DOCS:
            assert f'md/components/{doc.tag}.md' in snapshots

    def test_component_md_same_source_as_pages(self) -> None:
        button = next(doc for doc in DOCS if doc.tag == 'Button')
        text = component_md(button, 'en')
        assert text.startswith('# Button\n')
        assert '| `on_click` |' in text  # props 表与 HTML 页同一 props_table_md
        assert 'def demo_button()' in text  # demo 源码同 inspect.getsource

    def test_zh_snapshot_uses_translation(self) -> None:
        button = next(doc for doc in DOCS if doc.tag == 'Button')
        text = component_md(button, 'zh')
        assert '服务端可 patch' in text


class TestLlmsTxt:
    def test_llmstxt_shape(self) -> None:
        text = llms_txt(DOCS, base_url=BASE, locale='en')
        lines = text.splitlines()
        assert lines[0] == '# PyShade'
        assert lines[2].startswith('> ')
        assert any(line.startswith('## ') for line in lines)

    def test_links_point_to_md_snapshots(self) -> None:
        """定案:hash SPA 对 LLM 抓取是空 index.html,llms.txt 链接一律指 .md。"""
        text = llms_txt(DOCS, base_url=BASE, locale='en')
        links = re.findall(r'\((https?://[^)]+)\)', text)
        internal = [link for link in links if link.startswith(BASE)]
        assert internal, '至少要有站内链接'
        assert all(link.endswith('.md') for link in internal), internal

    def test_links_resolve_to_generated_snapshots(self) -> None:
        text = llms_txt(DOCS, base_url=BASE, locale='en')
        snapshots = md_snapshots(DOCS, 'en')
        for link in re.findall(rf'\({BASE}/en/([^)]+)\)', text):
            assert link in snapshots, f'llms.txt 链接目标缺快照:{link}'

    def test_llms_full_contains_everything(self) -> None:
        text = llms_full_txt(DOCS, 'en')
        for doc in DOCS:
            assert f'# {doc.tag}' in text


class TestAssembly:
    def test_inject_mock_before_app_js(self) -> None:
        html = '<head>\n    <script type="module" src="./app.js"></script>\n  </head>'
        out = inject_mock_script(html)
        assert out.index('demo-mock.js') < out.index('app.js"></script>')
        assert inject_mock_script(out) == out  # 幂等

    def test_redirect_html(self) -> None:
        html = redirect_html()
        assert 'navigator.language' in html
        assert 'hreflang="zh"' in html
        assert './en/' in html and './zh/' in html
