"""UI 字符串表:结构语言无关,只有文案分 locale(design.md §3.10 i18n 红利)。"""

from typing import Literal

Locale = Literal['en', 'zh']

LOCALES: tuple[Locale, ...] = ('en', 'zh')

_STRINGS: dict[str, dict[Locale, str]] = {
    'site_title': {'en': 'PyShade Docs', 'zh': 'PyShade 文档'},
    'tagline': {
        'en': 'Build modern desktop apps in pure Python — compiled to shadcn/ui React.',
        'zh': '纯 Python 构建现代桌面应用——编译成 shadcn/ui React。',
    },
    'nav_home': {'en': 'Home', 'zh': '首页'},
    'nav_components': {'en': 'Components', 'zh': '组件'},
    'nav_quickstart': {'en': 'Quickstart', 'zh': '快速开始'},
    'toggle_scheme': {'en': 'Toggle theme', 'zh': '明暗切换'},
    'switch_locale': {'en': '中文', 'zh': 'English'},
    'components_index_title': {'en': 'Components', 'zh': '组件一览'},
    'components_index_intro': {
        'en': 'Every component page is compiled from the same Pydantic DTOs the framework ships.',
        'zh': '每个组件页都由框架自身的 Pydantic DTO 编译而来(单点真相)。',
    },
    'live_demo': {'en': 'Live demo', 'zh': '在线演示'},
    'demo_source': {'en': 'Demo source', 'zh': '演示源码'},
    'props_heading': {'en': 'Props', 'zh': '属性'},
    'props_col_prop': {'en': 'Prop', 'zh': '属性'},
    'props_col_type': {'en': 'Type', 'zh': '类型'},
    'props_col_binding': {'en': 'Binding', 'zh': '绑定形态'},
    'props_col_default': {'en': 'Default', 'zh': '默认值'},
    'props_col_description': {'en': 'Description', 'zh': '说明'},
    'binding_event': {'en': 'event', 'zh': '事件'},
    'default_required': {'en': 'required', 'zh': '必填'},
    'mock_note': {
        'en': 'This static site simulates Python handlers in JS; run `pyshade dev` locally for the real backend.',
        'zh': '静态站用 JS 模拟 Python handler;本地 `pyshade dev` 才是真后端。',
    },
}


def t(key: str, locale: Locale) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        raise KeyError(f"i18n 缺键:{key}")
    return entry[locale]


def other_locale(locale: Locale) -> Locale:
    return 'zh' if locale == 'en' else 'en'
