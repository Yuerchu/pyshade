"""编译器测试:IR 构建、checks、完整 TSX 产出、golden 对比。"""

import json
import os
from enum import Enum
from pathlib import Path
from typing import ClassVar, cast

import pytest
from pydantic import BaseModel

from pyshade.app import ShadeApp
from pyshade.compiler import compile_app
from pyshade.compiler.checks import CompileError, check_app, check_page_ir
from pyshade.compiler.emit_app import emit_app, emit_manifest
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.emit_types import collect_enums, emit_types
from pyshade.compiler.ir import build_page_ir
from pyshade.compiler.writer import js_value
from pyshade.components import Button, ButtonVariant, Card, Input, PasswordInput, Switch, Text
from pyshade.components.base import Component
from pyshade.events import EventContext, Update
from pyshade.page import Page

GOLDEN_DIR = Path(__file__).parent / 'golden'
UPDATE_GOLDEN = os.environ.get('PYSHADE_UPDATE_GOLDEN') == '1'


def on_change(ctx: EventContext) -> None: ...


def on_submit(ctx: EventContext) -> list[Update]:
    return []


def on_remember(ctx: EventContext) -> None: ...


class LoginPage(Page):
    heading = Text('欢迎回来')
    username = Input(label='用户名', placeholder='请输入用户名', on_change=on_change)
    password = PasswordInput(label='密码', placeholder='请输入密码')
    remember = Switch(label='记住我', on_change=on_remember)
    submit = Button('登录', variant=ButtonVariant.DEFAULT, submit=True, on_click=on_submit)
    greeting = Text('', muted=True)

    card = Card(heading, username, password, remember, submit, greeting, title='登录', description='PyShade M0 演示')


class TestIR:
    def test_page_ir_shape(self) -> None:
        ir = build_page_ir(LoginPage)
        assert ir.name == 'LoginPage'
        assert len(ir.roots) == 1
        root = ir.roots[0]
        assert root.tag == 'Card'
        assert len(root.children) == 6

    def test_event_handler_ids(self) -> None:
        ir = build_page_ir(LoginPage)
        card = ir.roots[0]
        username_node = card.children[1]
        assert username_node.events[0].handler_id == 'LoginPage.username.on_change'

    def test_sensitive_flag(self) -> None:
        ir = build_page_ir(LoginPage)
        card = ir.roots[0]
        password_node = card.children[2]
        assert password_node.sensitive is True
        assert card.children[0].sensitive is False


class TestChecks:
    def test_js_reserved_word_rejected(self) -> None:
        class BadPage(Page):
            delete = Button('bad')

        ir = build_page_ir(BadPage)
        with pytest.raises(CompileError, match='保留字'):
            check_page_ir(ir)

    def test_literal_reserved_field_rejected(self) -> None:
        class NullFieldPage(Page):
            null = Button('bad')

        ir = build_page_ir(NullFieldPage)
        with pytest.raises(CompileError, match='保留字'):
            check_page_ir(ir)

    def test_reserved_page_name_rejected(self) -> None:
        # 页面名用作生成代码的函数名与 import 绑定,与字段名同受保留字约束
        page = cast('type[Page]', type('switch', (Page,), {'body': Text('x')}))
        with pytest.raises(CompileError, match='保留字或非法标识符'):
            check_app([build_page_ir(page)])

    def test_invalid_shade_tag_rejected(self) -> None:
        class EvilTag(Component):
            _shade_tag: ClassVar[str] = '*/}<button onClick={alert}>pwn</button>{/*'

        class EvilTagPage(Page):
            widget = EvilTag()

        ir = build_page_ir(EvilTagPage)
        with pytest.raises(CompileError, match='合法标识符'):
            check_page_ir(ir)

    def test_empty_shade_tag_rejected(self) -> None:
        class Untagged(Component):
            pass  # 基类默认 _shade_tag = '',此前静默发注释

        class UntaggedPage(Page):
            widget = Untagged()

        ir = build_page_ir(UntaggedPage)
        with pytest.raises(CompileError, match='合法标识符'):
            check_page_ir(ir)

    def test_valid_page_passes(self) -> None:
        ir = build_page_ir(LoginPage)
        check_page_ir(ir)


class TestVisibleGuard:
    def test_plain_false_emits_guard(self) -> None:
        class HiddenPage(Page):
            hidden = Text('hidden-text', visible=False)

        ir = build_page_ir(HiddenPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # 默认隐藏且服务端 Update(visible=True) 可翻转——此前三分支全不命中,组件恒渲染
        assert 'rt.ov("HiddenPage.hidden", "visible", false) && (' in tsx

    def test_plain_true_guard_unchanged(self) -> None:
        class ShownPage(Page):
            shown = Text('shown-text')

        ir = build_page_ir(ShownPage)
        tsx = emit_page(ir)
        assert 'rt.ov("ShownPage.shown", "visible", true) && (' in tsx


class TestJsValue:
    def test_nan_rejected(self) -> None:
        with pytest.raises(CompileError, match='非有限浮点数'):
            js_value(float('nan'))

    def test_inf_rejected(self) -> None:
        with pytest.raises(CompileError, match='非有限浮点数'):
            js_value(float('inf'))

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(CompileError, match='不支持的 prop 值类型'):
            js_value(object())

    def test_scalars_round_trip(self) -> None:
        assert js_value(1.5) == '1.5'
        assert js_value(True) == 'true'
        assert js_value(None) == 'null'


class TestEmitTypes:
    def test_enum_collection(self) -> None:
        ir = build_page_ir(LoginPage)
        enums = collect_enums([ir])
        names = [e.__name__ for e in enums]
        assert 'ButtonSize' in names
        assert 'ButtonVariant' in names

    def test_types_gen_content(self) -> None:
        ir = build_page_ir(LoginPage)
        enums = collect_enums([ir])
        ts = emit_types(enums)
        assert 'export type ButtonVariant =' in ts
        assert '"destructive"' in ts

    def test_enum_value_with_quote_escaped(self) -> None:
        class TrickyEnum(Enum):
            EVIL = 'say "hi" \\ backslash'

        ts = emit_types([TrickyEnum])
        assert '\\"hi\\"' in ts  # json.dumps 转义,产物是合法 TS

    def test_non_str_enum_rejected(self) -> None:
        class NumberEnum(Enum):
            ONE = 1

        with pytest.raises(CompileError, match='不是 str'):
            emit_types([NumberEnum])

    def test_unmappable_model_field_rejected(self) -> None:
        class DeepModel(BaseModel):
            tags: list[str] = []

        with pytest.raises(CompileError, match='无法映射'):
            emit_types([], [DeepModel])


def golden_compare(name: str, content: str) -> None:
    path = GOLDEN_DIR / name
    if UPDATE_GOLDEN:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')
        return
    if not path.exists():
        pytest.skip(f"golden file {path} missing; run with PYSHADE_UPDATE_GOLDEN=1")
    expected = path.read_text(encoding='utf-8')
    assert content == expected, f"golden mismatch: {path}\nrun PYSHADE_UPDATE_GOLDEN=1 to update"


class TestGolden:
    def test_login_page_tsx(self) -> None:
        ir = build_page_ir(LoginPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        assert '由 pyshade 编译器生成' in tsx
        assert 'usePageRuntime' in tsx
        assert 'collectValues' in tsx
        assert 'passwordRef' in tsx
        assert 'usernameValue' in tsx
        assert 'LoginPage.submit.on_click' in tsx
        golden_compare('LoginPage.gen.tsx', tsx)

    def test_app_gen(self) -> None:
        ir = build_page_ir(LoginPage)
        tsx = emit_app([ir])
        assert 'LoginPage' in tsx
        golden_compare('app.gen.tsx', tsx)

    def test_manifest_json(self) -> None:
        ir = build_page_ir(LoginPage)
        manifest = emit_manifest([ir])
        data = json.loads(manifest)
        assert 'LoginPage.submit.on_click' in data['pages']['LoginPage']
        golden_compare('manifest.json', manifest)

    def test_types_gen(self) -> None:
        ir = build_page_ir(LoginPage)
        enums = collect_enums([ir])
        ts = emit_types(enums)
        golden_compare('types.gen.ts', ts)


class TestCompileApp:
    def test_compile_to_directory(self, tmp_path: Path) -> None:
        app = ShadeApp(pages=[LoginPage])
        compile_app(app, tmp_path)
        assert (tmp_path / 'pages' / 'LoginPage.gen.tsx').exists()
        assert (tmp_path / 'app.gen.tsx').exists()
        assert (tmp_path / 'types.gen.ts').exists()
        assert (tmp_path / 'manifest.json').exists()
