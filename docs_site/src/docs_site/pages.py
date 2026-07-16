"""页面工厂:HomePage / ComponentsPage / QuickstartPage + 逐组件动态页。

逐组件页 = `type(f'{tag}Page', (Page,), ns)`(spike 已固化:`__init_subclass__` 经
`vars(cls)` 收集,type() 三参 namespace 保序);页面 = 摘要(docstring i18n)+ props 表
(introspect 渲染 markdown)+ live demo + 演示源码,全量 dogfood 自家组件。
"""

import inspect
from typing import Any

from docs_site.content import en_summaries, guide_md, zh_props
from docs_site.demos import DEMOS, DemoFactory
from docs_site.i18n import Locale, t
from docs_site.nav import chrome, mock_note
from pyshade.components import Button, ButtonVariant, CodeBlock, Component, Heading, Markdown, Stack, Text
from pyshade.docs import ComponentDoc, FieldDoc, collect_components
from pyshade.nav import navigate
from pyshade.page import Page

SERVER_DEMO_TAGS = frozenset({'AlertDialog', 'Button', 'Each', 'PasswordInput'})
"""demo 含 Python handler 的组件:静态站上由 demo-mock.js 模拟,页面带诚实标注。"""


def _cell(text: str) -> str:
    return text.replace('|', '\\|').replace('\n', ' ')


def _field_row(entry: FieldDoc, locale: Locale, zh_fields: dict[str, str]) -> str:
    if entry.event_kind is not None:
        binding = f"{t('binding_event', locale)}: {entry.event_kind}"
    else:
        binding = ', '.join(entry.bindings)
    type_display = entry.type_display
    if entry.enum_values is not None:
        type_display += f" ({' / '.join(entry.enum_values)})"
    default = entry.default_display if entry.default_display is not None else t('default_required', locale)
    description = zh_fields.get(entry.name, '') if locale == 'zh' else (entry.description or '')
    cells = (f'`{entry.name}`', _cell(type_display), _cell(binding), _cell(f'`{default}`'), _cell(description))
    return f'| {" | ".join(cells)} |'


def props_table_md(doc: ComponentDoc, locale: Locale) -> str:
    zh_fields = zh_props().get(doc.class_name, {}) if locale == 'zh' else {}
    header = (
        f"| {t('props_col_prop', locale)} | {t('props_col_type', locale)} | {t('props_col_binding', locale)} "
        f"| {t('props_col_default', locale)} | {t('props_col_description', locale)} |"
    )
    rows = [header, '|---|---|---|---|---|']
    rows.extend(_field_row(entry, locale, zh_fields) for entry in doc.fields)
    return '\n'.join(rows)


def _stacked(ns: dict[str, Any]) -> dict[str, Any]:
    """把命名空间里的全部组件收进 Stack 文档流(命名字段被容器引用后自动移出根级)。"""
    components = [value for value in ns.values() if isinstance(value, Component)]
    ns['page_stack'] = Stack(*components)
    return ns


def component_page(doc: ComponentDoc, locale: Locale) -> type[Page]:
    factory: DemoFactory = DEMOS[doc.tag]
    summary = doc.docstring if locale == 'zh' else en_summaries()[doc.class_name]

    ns: dict[str, Any] = {}
    ns.update(chrome(locale))
    ns['doc_title'] = Heading(doc.tag, level=1)
    ns['doc_summary'] = Markdown(summary)
    ns['props_title'] = Heading(t('props_heading', locale), level=3)
    ns['props_table'] = Markdown(props_table_md(doc, locale))
    ns['demo_title'] = Heading(t('live_demo', locale), level=3)
    if doc.tag in SERVER_DEMO_TAGS:
        ns.update(mock_note(locale))
    ns.update(factory())
    ns['source_title'] = Heading(t('demo_source', locale), level=3)
    ns['source_code'] = CodeBlock(inspect.getsource(factory), language='python')
    return type(f'{doc.tag}Page', (Page,), _stacked(ns))


def home_page(locale: Locale) -> type[Page]:
    ns: dict[str, Any] = {}
    ns.update(chrome(locale))
    ns['home_title'] = Heading(t('site_title', locale), level=1)
    ns['home_tagline'] = Text(t('tagline', locale), muted=True)
    ns['home_body'] = Markdown(guide_md('home', locale))
    return type('HomePage', (Page,), _stacked(ns))


def components_index_page(locale: Locale, docs: list[ComponentDoc]) -> type[Page]:
    ns: dict[str, Any] = {}
    ns.update(chrome(locale))
    ns['idx_title'] = Heading(t('components_index_title', locale), level=1)
    ns['idx_intro'] = Text(t('components_index_intro', locale), muted=True)
    for doc in docs:
        ns[f'goto_{doc.tag.lower()}'] = Button(
            doc.tag, variant=ButtonVariant.OUTLINE, on_click=navigate(f'{doc.tag}Page')
        )
    return type('ComponentsPage', (Page,), _stacked(ns))


def quickstart_page(locale: Locale) -> type[Page]:
    ns: dict[str, Any] = {}
    ns.update(chrome(locale))
    ns['guide_title'] = Heading(t('nav_quickstart', locale), level=1)
    ns['guide_body'] = Markdown(guide_md('quickstart', locale))
    return type('QuickstartPage', (Page,), _stacked(ns))


def all_pages(locale: Locale) -> list[type[Page]]:
    docs = collect_components()
    pages: list[type[Page]] = [
        home_page(locale),
        components_index_page(locale, docs),
        quickstart_page(locale),
    ]
    pages.extend(component_page(doc, locale) for doc in docs)
    return pages
