"""Theme 主题口子:校验护栏、token 映射、theme.gen.css 发射、模型-CSS 对账、bundle 注入。"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyshade.app import ShadeApp
from pyshade.bundler._html import inject_theme_style
from pyshade.compiler import compile_app
from pyshade.compiler.emit_theme import emit_theme_css
from pyshade.components import Text
from pyshade.page import Page
from pyshade.theme import Theme, theme_tokens

REPO = Path(__file__).parent.parent


class ThemeProbePage(Page):
    hello = Text('theme')


class TestThemeModel:
    def test_unknown_token_rejected_at_construction(self) -> None:
        with pytest.raises(ValidationError, match='extra'):
            Theme(nope='red')  # pyright: ignore[reportCallIssue]

    def test_empty_value_rejected(self) -> None:
        with pytest.raises(ValidationError, match='空串'):
            Theme(primary='   ')

    def test_css_injection_guard(self) -> None:
        with pytest.raises(ValidationError, match='注入护栏'):
            Theme(primary='red; } body { display: none')

    def test_valid_values_pass_through(self) -> None:
        theme = Theme(primary='oklch(0.55 0.18 260)', border='#e5e5e5', radius='0.75rem', ring='var(--primary)')
        assert theme_tokens(theme) == {
            'primary': 'oklch(0.55 0.18 260)',
            'border': '#e5e5e5',
            'ring': 'var(--primary)',
            'radius': '0.75rem',
        }

    def test_snake_to_kebab(self) -> None:
        assert theme_tokens(Theme(primary_foreground='white')) == {'primary-foreground': 'white'}


class TestModelCssParity:
    def test_fields_mirror_index_css_root_tokens(self) -> None:
        """防漂移:index.css 加 token 时 Theme 必须同步(反之亦然)。"""
        index_css = (REPO / 'frontend' / 'src' / 'index.css').read_text(encoding='utf-8')
        root_block = index_css.split(':root {', 1)[1].split('}', 1)[0]
        css_tokens = set(re.findall(r'--([a-z0-9-]+):', root_block))
        model_tokens = {name.replace('_', '-') for name in Theme.model_fields}
        assert model_tokens == css_tokens


class TestEmitAndWire:
    def test_emit_theme_css_only_set_fields(self) -> None:
        css = emit_theme_css(Theme(primary='red', radius='1rem'))
        assert css == ('/* 由 pyshade 编译器生成 — 请勿手改。 */\n:root {\n  --primary: red;\n  --radius: 1rem;\n}\n')

    def test_compile_app_emits_theme_css(self, tmp_path: Path) -> None:
        app = ShadeApp(pages=[ThemeProbePage], theme=Theme(primary='red'))
        compile_app(app, tmp_path)
        assert (tmp_path / 'theme.gen.css').read_text(encoding='utf-8').count('--primary: red;') == 1

    def test_compile_app_without_theme_zero_artifact(self, tmp_path: Path) -> None:
        compile_app(ShadeApp(pages=[ThemeProbePage]), tmp_path)
        assert not (tmp_path / 'theme.gen.css').exists()

    def test_inject_after_style_link(self) -> None:
        html = '<head>\n    <link rel="stylesheet" href="./style.css" />\n  </head>'
        out = inject_theme_style(html, ':root {\n  --primary: red;\n}\n')
        assert out.index('style.css') < out.index('data-pyshade-theme')
        assert '--primary: red;' in out
