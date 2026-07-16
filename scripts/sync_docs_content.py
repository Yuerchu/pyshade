"""同步文档站翻译表的键集合(docs_site/content):新组件/新字段补占位,已有翻译保留。

- zh/props.toml:组件类名 → {字段: 中文描述};缺键以英文 description 占位;
- en/extra.toml:[docstrings] 组件类名 → 英文摘要;缺键以中文 docstring 原文占位。

tests/docs_site 的对账测试红了就跑这个,再人工翻译占位值。
"""

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))

from pyshade.docs import collect_components  # noqa: E402


def _quote(value: str) -> str:
    escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
    return f'"{escaped}"'


def main() -> int:
    docs = collect_components()
    content = REPO / 'docs_site' / 'content'

    props_path = content / 'zh' / 'props.toml'
    existing_props: dict[str, dict[str, str]] = {}
    if props_path.exists():
        existing_props = tomllib.loads(props_path.read_text(encoding='utf-8'))
    lines = ['# 组件字段描述的中文翻译表(键集合与 docs.introspect 对账,tests/docs_site 防漂移)', '']
    placeholders = 0
    for doc in docs:
        lines.append(f'[{doc.class_name}]')
        current = existing_props.get(doc.class_name, {})
        for field in doc.fields:
            value = current.get(field.name)
            if value is None:
                value = field.description or ''
                placeholders += 1
            lines.append(f'{field.name} = {_quote(value)}')
        lines.append('')
    props_path.parent.mkdir(parents=True, exist_ok=True)
    props_path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')

    extra_path = content / 'en' / 'extra.toml'
    existing_extra: dict[str, str] = {}
    if extra_path.exists():
        existing_extra = tomllib.loads(extra_path.read_text(encoding='utf-8')).get('docstrings', {})
    lines = ['# 组件类 docstring 的英文摘要(en 页使用;键集合与组件类名对账)', '', '[docstrings]']
    for doc in docs:
        value = existing_extra.get(doc.class_name)
        if value is None:
            value = doc.docstring
            placeholders += 1
        lines.append(f'{doc.class_name} = {_quote(value)}')
    lines.append('')
    extra_path.parent.mkdir(parents=True, exist_ok=True)
    extra_path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')

    print(f"synced {len(docs)} components; {placeholders} placeholder value(s) need translation")
    return 0


if __name__ == '__main__':
    sys.exit(main())
