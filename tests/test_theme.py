"""Theme 主题口子:校验护栏、token 映射、theme.gen.css 三段发射、模型-CSS 双向对账、bundle 注入。"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyshade.app import ShadeApp
from pyshade.bundler._html import inject_scheme_boot, inject_theme_style, scheme_boot_script
from pyshade.compiler import compile_app
from pyshade.compiler.emit_theme import emit_theme_css
from pyshade.components import Text
from pyshade.page import Page
from pyshade.theme import MODE_INDEPENDENT_TOKENS, Theme, ThemeTokens, theme_tokens

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

    def test_dark_nested_tokens(self) -> None:
        theme = Theme(primary='white', dark=ThemeTokens(primary='black'))
        assert theme.dark is not None
        assert theme_tokens(theme.dark) == {'primary': 'black'}
        # dark 字段本身不进 token 表
        assert theme_tokens(theme) == {'primary': 'white'}

    def test_dark_guard_applies(self) -> None:
        with pytest.raises(ValidationError, match='注入护栏'):
            Theme(dark=ThemeTokens(primary='x; } * { color: red'))
        with pytest.raises(ValidationError, match='extra'):
            Theme(dark=ThemeTokens(nope='red'))  # pyright: ignore[reportCallIssue]


class TestModelCssParity:
    def _block(self, selector: str) -> set[str]:
        index_css = (REPO / 'frontend' / 'src' / 'index.css').read_text(encoding='utf-8')
        block = index_css.split(f'{selector} {{', 1)[1].split('}', 1)[0]
        return set(re.findall(r'--([a-z0-9-]+):', block))

    def test_fields_mirror_index_css_root_tokens(self) -> None:
        """防漂移:index.css 加 token 时 ThemeTokens 必须同步(反之亦然)。"""
        model_tokens = {name.replace('_', '-') for name in ThemeTokens.model_fields}
        assert model_tokens == self._block(':root')

    def test_dark_block_mirrors_model(self) -> None:
        """防漂移:.dark 块 = 全部 token - 模式无关 token(radius 不在暗色重定义)。"""
        model_tokens = {name.replace('_', '-') for name in ThemeTokens.model_fields}
        mode_independent = {name.replace('_', '-') for name in MODE_INDEPENDENT_TOKENS}
        assert self._block('.dark') == model_tokens - mode_independent

    def test_theme_only_adds_dark_field(self) -> None:
        assert set(Theme.model_fields) - set(ThemeTokens.model_fields) == {'dark'}


class TestEmitAndWire:
    def test_emit_three_segments(self) -> None:
        css = emit_theme_css(Theme(primary='red', radius='1rem', dark=ThemeTokens(primary='pink')))
        assert css == (
            '/* 由 pyshade 编译器生成 — 请勿手改。 */\n'
            ':root {\n  --radius: 1rem;\n}\n'
            ':root:not(.dark) {\n  --primary: red;\n}\n'
            '.dark {\n  --primary: pink;\n}\n'
        )

    def test_emit_skips_empty_segments(self) -> None:
        # 只有暗色:不发 :root 与 :root:not(.dark)
        css = emit_theme_css(Theme(dark=ThemeTokens(background='black')))
        assert ':root' not in css
        assert '.dark {\n  --background: black;\n}' in css

    def test_light_uses_not_dark_selector(self) -> None:
        """亮色段用 :root:not(.dark) 提升 specificity:内联 <style> 后到也不压过内置暗色默认值。"""
        css = emit_theme_css(Theme(primary='red'))
        assert ':root:not(.dark) {\n  --primary: red;\n}' in css
        assert ':root {\n' not in css.replace(':root:not(.dark) {\n', '')

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


class TestSchemeBoot:
    def test_boot_script_variants(self) -> None:
        # system:localStorage 显式选择 ?? matchMedia;dark/light:显式选择 ?? app 默认
        assert 'prefers-color-scheme' in scheme_boot_script('system')
        assert scheme_boot_script('dark').count('s !== "light"') == 1
        assert scheme_boot_script('light').count('s === "dark"') == 1

    def test_boot_injected_before_style_link(self) -> None:
        html = '<head>\n    <link rel="stylesheet" href="./style.css" />\n  </head>'
        out = inject_scheme_boot(html, 'system')
        assert out.index('data-pyshade-scheme') < out.index('style.css')
        assert 'pyshade:color-scheme' in out
