"""M1 表达式编译:binding 分类、G 规则校验、SettingsPage golden。"""

import warnings

import pytest

from pyshade.compiler.checks import CompileError, check_page_ir
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.ir import build_page_ir
from pyshade.components import Button, Card, Input, PasswordInput, Switch, Text
from pyshade.events import EventContext, Update
from pyshade.expr import ClientVal, ExprType, PropRef, value_of
from pyshade.page import Page
from tests.compiler.test_compiler import golden_compare


def on_save(ctx: EventContext) -> list[Update]:
    return []


class SettingsPage(Page):
    """三形态演示:ClientVal(client_bind)/ Expr(内联 JS)/ plain(rt.ov)。"""

    thinking = ClientVal(True)
    dark = ClientVal(False)
    nick = ClientVal('')

    thinking_switch = Switch(label='思考模式', checked=thinking)
    dark_switch = Switch(label='深色模式', checked=dark)
    effort = Input(label='思考力度', placeholder='low / medium / high', disabled=~thinking)
    nickname = Input(label='昵称', value=nick)
    greeting = Text(text='你好,' + nick + '!', visible=nick != '')
    echo = Text(text='输入了:' + value_of(effort), visible=value_of(effort) != '', muted=True)
    both = Text('思考与深色已同时开启', visible=thinking & dark, muted=True)
    save = Button('保存', submit=True, on_click=on_save)

    card = Card(
        thinking_switch,
        dark_switch,
        effort,
        nickname,
        greeting,
        echo,
        both,
        save,
        title='设置',
        description='M1 表达式演示',
    )


class TestBindingClassification:
    def test_client_bind_on_controlled_prop(self) -> None:
        ir = build_page_ir(SettingsPage)
        switch_node = ir.roots[0].children[0]
        checked = next(p for p in switch_node.props if p.name == 'checked')
        assert checked.binding == 'client_bind'

    def test_expr_prop(self) -> None:
        ir = build_page_ir(SettingsPage)
        effort_node = ir.roots[0].children[2]
        disabled = next(p for p in effort_node.props if p.name == 'disabled')
        assert disabled.binding == 'expr'

    def test_plain_prop(self) -> None:
        ir = build_page_ir(SettingsPage)
        effort_node = ir.roots[0].children[2]
        label = next(p for p in effort_node.props if p.name == 'label')
        assert label.binding == 'plain'

    def test_client_val_on_non_controlled_prop_is_expr(self) -> None:
        # ClientVal 出现在非受控 prop 上是只读引用,不是写绑定
        class ReadOnlyPage(Page):
            flag = ClientVal(True)
            switch = Switch(label='开关', checked=flag)
            text = Text('hi', visible=flag)

        ir = build_page_ir(ReadOnlyPage)
        text_node = next(n for n in ir.roots if n.tag == 'Text')
        visible = next(p for p in text_node.props if p.name == 'visible')
        assert visible.binding == 'expr'

    def test_page_ir_carries_client_vals(self) -> None:
        ir = build_page_ir(SettingsPage)
        assert list(ir.client_vals) == ['thinking', 'dark', 'nick']


class TestExprChecks:
    def test_settings_page_passes(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            check_page_ir(build_page_ir(SettingsPage))

    def test_multiple_writers_rejected(self) -> None:
        class MultiWriterPage(Page):
            flag = ClientVal(True)
            a = Switch(label='A', checked=flag)
            b = Switch(label='B', checked=flag)

        with pytest.raises(CompileError, match='多个写者'):
            check_page_ir(build_page_ir(MultiWriterPage))

    def test_unowned_client_val_rejected(self) -> None:
        class InlinePage(Page):
            text = Text('hi', visible=ClientVal(True))

        with pytest.raises(CompileError, match='未声明为页面字段'):
            check_page_ir(build_page_ir(InlinePage))

    def test_unowned_client_bind_rejected(self) -> None:
        class InlineBindPage(Page):
            toggle = Switch(label='开关', checked=ClientVal(True))

        with pytest.raises(CompileError, match='未声明为页面字段'):
            check_page_ir(build_page_ir(InlineBindPage))

    def test_cross_page_client_val_rejected(self) -> None:
        class OwnerPage(Page):
            flag = ClientVal(True)
            switch = Switch(label='开关', checked=flag)

        class ThiefPage(Page):
            text = Text('hi', visible=OwnerPage.flag)

        with pytest.raises(CompileError, match='其他页面'):
            check_page_ir(build_page_ir(ThiefPage))

    def test_dead_prop_ref_rejected(self) -> None:
        orphan = Input(label='游离组件')

        class DeadRefPage(Page):
            text = Text(text=value_of(orphan))

        with pytest.raises(CompileError, match='未挂载'):
            check_page_ir(build_page_ir(DeadRefPage))

    def test_cross_page_prop_ref_rejected(self) -> None:
        class SourcePage(Page):
            field = Input(label='源')

        class LeechPage(Page):
            text = Text(text=value_of(SourcePage.field))

        with pytest.raises(CompileError, match='跨页面'):
            check_page_ir(build_page_ir(LeechPage))

    def test_type_mismatch_rejected(self) -> None:
        class MismatchPage(Page):
            name = ClientVal('x')
            field = Input(value=name)
            # str 表达式绑到 bool prop:pyright 层(泛型不变)与 G 规则双层拒绝
            text = Text('hi', visible=name)  # pyright: ignore[reportArgumentType]

        with pytest.raises(CompileError, match='不匹配'):
            check_page_ir(build_page_ir(MismatchPage))

    def test_client_bind_type_mismatch_rejected(self) -> None:
        # pydantic is-instance 不校验泛型参数,类型匹配由 G 规则把关
        class BindMismatchPage(Page):
            name = ClientVal('x')
            toggle = Switch(label='开关', checked=name)  # pyright: ignore[reportArgumentType]

        with pytest.raises(CompileError, match='不匹配'):
            check_page_ir(build_page_ir(BindMismatchPage))

    def test_sensitive_prop_ref_rejected(self) -> None:
        # value_of 运行时已拒绝敏感组件;直接构造 PropRef 验证编译层防御纵深
        class SensitiveRefPage(Page):
            password = PasswordInput(label='密码')
            text = Text('hi')

        ir = build_page_ir(SensitiveRefPage)
        text_node = next(n for n in ir.roots if n.tag == 'Text')
        stolen: PropRef[str] = PropRef(SensitiveRefPage.password, 'value', ExprType.STR)
        text_node.props = [
            p if p.name != 'text' else type(p)(name='text', default_value=stolen, is_enum=False, binding='expr')
            for p in text_node.props
        ]
        with pytest.raises(CompileError, match='敏感'):
            check_page_ir(ir)

    def test_unbound_referenced_client_val_warns(self) -> None:
        class ConstPage(Page):
            flag = ClientVal(True)
            text = Text('hi', visible=flag)

        with pytest.warns(UserWarning, match='没有任何受控组件绑定'):
            check_page_ir(build_page_ir(ConstPage))

    def test_var_name_collision_rejected(self) -> None:
        # 匿名组件 CollisionPage.wrapper[0] 的路径变量名是 wrapper_0
        class CollisionPage(Page):
            wrapper_0 = ClientVal(True)
            wrapper = Card(Input(label='匿名'), title='容器')
            probe = Switch(label='占位', checked=wrapper_0)

        with pytest.raises(CompileError, match='变量名冲突'):
            check_page_ir(build_page_ir(CollisionPage))


class TestSettingsGolden:
    def test_settings_page_tsx(self) -> None:
        ir = build_page_ir(SettingsPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # client_bind:Switch 与 ClientVal 共用 useState
        assert 'const [thinkingValue, setThinkingValue] = useState<boolean>(true);' in tsx
        assert 'checked={thinkingValue}' in tsx
        assert 'setThinkingValue(checked)' in tsx
        # expr:内联 JS,不包 rt.ov
        assert 'disabled={!thinkingValue}' in tsx
        assert '{(nickValue !== "") && (' in tsx
        assert '{(thinkingValue && darkValue) && (' in tsx
        # PropRef:引用受控组件的 useState 变量
        assert '{("输入了:" + effortValue)' in tsx or '"输入了:" + effortValue' in tsx
        # boundProps 汇总
        assert 'usePageRuntime({ boundProps: [' in tsx
        # collectValues 追加 ClientVal 条目
        assert 'nick: nickValue,' in tsx
        golden_compare('SettingsPage.gen.tsx', tsx)
