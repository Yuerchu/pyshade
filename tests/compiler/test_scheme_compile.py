"""M4 dark mode 编译:scheme action 发射(零 IPC)、submit 互斥、注册表跳过、App colorScheme。"""

import pytest

from pyshade.app import ShadeApp
from pyshade.compiler.checks import CompileError, check_page_ir
from pyshade.compiler.emit_app import emit_app
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.ir import build_page_ir
from pyshade.components import Button, ButtonVariant, Card, Text
from pyshade.events import EventRegistry
from pyshade.page import Page
from pyshade.scheme import set_color_scheme, toggle_color_scheme
from tests.compiler.test_compiler import golden_compare


class SchemePage(Page):
    hint = Text('配色切换演示')
    toggle = Button('明暗切换', variant=ButtonVariant.GHOST, on_click=toggle_color_scheme())
    force_dark = Button('暗色', on_click=set_color_scheme('dark'))
    follow = Button('跟随系统', on_click=set_color_scheme('system'))

    card = Card(hint, toggle, force_dark, follow, title='配色')


class TestSchemeGolden:
    def test_scheme_page_tsx(self) -> None:
        ir = build_page_ir(SchemePage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # 零 IPC:编译为 rt.setColorScheme,不发 rt.fire
        assert 'onClick={() => rt.setColorScheme("toggle")}' in tsx
        assert 'onClick={() => rt.setColorScheme("dark")}' in tsx
        assert 'onClick={() => rt.setColorScheme("system")}' in tsx
        assert 'rt.fire' not in tsx
        golden_compare('SchemePage.gen.tsx', tsx)

    def test_app_emits_color_scheme(self) -> None:
        tsx = emit_app([build_page_ir(SchemePage)])
        assert 'colorScheme="system"' in tsx
        dark = emit_app([build_page_ir(SchemePage)], color_scheme='dark')
        assert 'colorScheme="dark"' in dark


class TestSchemeChecks:
    def test_submit_scheme_conflict(self) -> None:
        class SubmitSchemePage(Page):
            btn = Button('提交并切换', submit=True, on_click=toggle_color_scheme())

        with pytest.raises(CompileError, match='submit=True'):
            check_page_ir(build_page_ir(SubmitSchemePage))

    def test_registry_skips_scheme_actions(self) -> None:
        registry = EventRegistry.from_app(ShadeApp(pages=[SchemePage]))
        assert len(registry) == 0  # 客户端 action 零 IPC,无 handlerId
