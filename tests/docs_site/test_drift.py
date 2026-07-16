"""文档站防漂移网:demos / 翻译表 / mock HANDLERS 与框架注册表的键集合对账。

加组件不加文档页、加字段不补翻译、加 handler 不补 mock——任何一条都在这里变红。
"""

import re
from pathlib import Path

from docs_site.app import make_app
from docs_site.demos import DEMOS

from docs_site.content import en_summaries, zh_props
from pyshade.docs import collect_components
from pyshade.events import EventRegistry

REPO = Path(__file__).resolve().parents[2]
MOCK_JS = REPO / 'docs_site' / 'assets' / 'demo-mock.js'

DOCS = collect_components()


class TestDemosRegistry:
    def test_demos_cover_all_emitters(self) -> None:
        from pyshade.compiler.emit_page import EMITTERS

        assert set(DEMOS) == set(EMITTERS)


class TestTranslationTables:
    def test_zh_props_keys_match_introspect(self) -> None:
        table = zh_props()
        expected = {doc.class_name: {f.name for f in doc.fields} for doc in DOCS}
        actual = {name: set(fields) for name, fields in table.items()}
        assert actual == expected, "zh props.toml 键集合漂移 → 跑 scripts/sync_docs_content.py 后补翻译"

    def test_en_summaries_keys_match(self) -> None:
        expected = {doc.class_name for doc in DOCS}
        assert set(en_summaries()) == expected, "en extra.toml 键集合漂移 → 跑 scripts/sync_docs_content.py 后补英译"


class TestAppShape:
    def test_component_pages_cover_all_tags(self) -> None:
        app = make_app('en')
        page_names = {page.__name__ for page in app.pages}
        missing = {f'{doc.tag}Page' for doc in DOCS} - page_names
        assert not missing, f"缺组件页:{sorted(missing)}"
        assert {'HomePage', 'ComponentsPage', 'QuickstartPage'} <= page_names

    def test_mock_handlers_match_registry(self) -> None:
        registry = EventRegistry.from_app(make_app('zh'))
        pattern = re.compile(r'"([A-Za-z]+Page\.[A-Za-z0-9_]+\.[a-z_]+)":')
        mocked = set(pattern.findall(MOCK_JS.read_text(encoding='utf-8')))
        assert mocked == set(registry), (
            f"demo-mock.js HANDLERS 与 EventRegistry 漂移:mock 独有 {sorted(mocked - set(registry))},"
            f"缺口 {sorted(set(registry) - mocked)}"
        )
