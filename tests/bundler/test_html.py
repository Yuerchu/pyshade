"""index.html 的 title/lang 注入(发版前审查):此前 <title> 恒为模板的 "pyshade app"、
<html lang> 硬编码——en 文档站声明 zh-CN,SEO/无障碍/翻译提示全错。"""

from pathlib import Path

import pytest

from pyshade.app import ShadeApp
from pyshade.bundler._assets import FrontendAssets
from pyshade.bundler._html import set_lang, set_title, write_static
from pyshade.components import Text
from pyshade.page import Page

_TEMPLATE = (
    '<!doctype html>\n<html lang="en">\n  <head>\n    <title>pyshade app</title>\n'
    '    <link rel="stylesheet" href="./style.css" />\n  </head>\n</html>\n'
)


class TestSetTitle:
    def test_replaces_template_title(self) -> None:
        assert '<title>My Docs</title>' in set_title(_TEMPLATE, 'My Docs')
        assert 'pyshade app' not in set_title(_TEMPLATE, 'My Docs')

    def test_html_escaped(self) -> None:
        out = set_title(_TEMPLATE, '<A&B>')
        assert '<title>&lt;A&amp;B&gt;</title>' in out


class TestSetLang:
    def test_replaces_lang_attribute(self) -> None:
        assert '<html lang="zh-CN">' in set_lang(_TEMPLATE, 'zh-CN')

    def test_only_first_occurrence(self) -> None:
        doubled = _TEMPLATE + '<html lang="en">'
        assert set_lang(doubled, 'fr').count('lang="fr"') == 1


class TestShadeAppLang:
    def test_default_en(self) -> None:
        class LangProbePage(Page):
            hello = Text('lang')

        assert ShadeApp(pages=[LangProbePage]).lang == 'en'
        assert ShadeApp(pages=[LangProbePage], lang='zh-CN').lang == 'zh-CN'

    def test_invalid_lang_rejected(self) -> None:
        class LangProbePage2(Page):
            hello = Text('lang')

        with pytest.raises(ValueError, match='BCP 47'):
            ShadeApp(pages=[LangProbePage2], lang='bad lang!"')


def test_write_static_end_to_end(tmp_path: Path) -> None:
    (tmp_path / 'index.html').write_text(_TEMPLATE, encoding='utf-8')
    (tmp_path / 'style.css').write_text(':root {}\n', encoding='utf-8')
    (tmp_path / 'vendor-manifest.json').write_text('{}', encoding='utf-8')
    assets = FrontendAssets(
        src_dir=tmp_path,
        node_modules=tmp_path,
        style_css=tmp_path / 'style.css',
        index_html=tmp_path / 'index.html',
        vendor_stamp=tmp_path / 'vendor-manifest.json',
    )
    out = tmp_path / 'out'
    out.mkdir()
    write_static(out, assets, title='PyShade 文档', lang='zh-CN')
    html = (out / 'index.html').read_text(encoding='utf-8')
    assert '<title>PyShade 文档</title>' in html
    assert '<html lang="zh-CN">' in html
    assert 'data-pyshade-scheme' in html  # scheme boot 注入不受 title/lang 替换影响
