"""构建期内容装载:guides markdown / zh props 翻译表 / en docstring 英译表。

翻译表与代码内 canonical(英文 Field description / 中文类 docstring)的键集合
由 tests/docs_site 对账,加字段/组件不补翻译即红。
"""

import sys
from functools import cache
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

CONTENT_DIR = Path(__file__).resolve().parents[2] / 'content'


def guide_md(slug: str, locale: str) -> str:
    return (CONTENT_DIR / locale / 'guides' / f'{slug}.md').read_text(encoding='utf-8')


@cache
def zh_props() -> dict[str, dict[str, str]]:
    """组件类名 → {字段名: 中文描述};en 页直接用代码内英文 description。"""
    with (CONTENT_DIR / 'zh' / 'props.toml').open('rb') as fh:
        return tomllib.load(fh)


@cache
def en_summaries() -> dict[str, str]:
    """组件类名 → 英文摘要(类 docstring 是中文,en 页用这份英译)。"""
    with (CONTENT_DIR / 'en' / 'extra.toml').open('rb') as fh:
        data = tomllib.load(fh)
    return data['docstrings']
