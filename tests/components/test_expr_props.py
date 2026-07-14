"""Pydantic union 冒烟(M1 计划风险门):`T | Expr[T]` prop 必须按 is-instance 保真通过。

若 smart union 出现吞值/深拷贝/误转型,M1 表达式主线的落点(prop 直接持有 Expr 节点)
不成立,需切换 InstanceOf 退路——所以此文件先于编译器扩展落地。
"""

import pytest
from pydantic import ValidationError

from pyshade.components import Input, PasswordInput, Switch, Text
from pyshade.expr import ClientVal, Expr, UnaryNot


class TestExprPropUnion:
    def test_switch_checked_keeps_client_val_identity(self) -> None:
        thinking = ClientVal(True)
        switch = Switch(checked=thinking)
        assert switch.checked is thinking

    def test_plain_bool_stays_bool(self) -> None:
        switch = Switch(checked=True)
        assert switch.checked is True

    def test_composite_expr_prop_keeps_identity(self) -> None:
        thinking = ClientVal(True)
        expr = ~thinking
        field = Input(disabled=expr)
        assert field.disabled is expr

    def test_controlled_prop_rejects_composite_expr(self) -> None:
        # 受控 prop 只接受裸 ClientVal(唯一写者);复合表达式不可写,构造期即拒绝
        thinking = ClientVal(True)
        with pytest.raises(ValidationError):
            Switch(checked=~thinking)  # pyright: ignore[reportArgumentType]

    def test_text_str_expr(self) -> None:
        nick = ClientVal('世界')
        text = Text(text='你好,' + nick)
        assert isinstance(text.text, Expr)

    def test_visible_expr_on_any_component(self) -> None:
        thinking = ClientVal(True)
        text = Text('hi', visible=thinking)
        password = PasswordInput(label='密码', visible=~thinking)
        assert text.visible is thinking
        assert isinstance(password.visible, UnaryNot)

    def test_model_copy_preserves_expr_identity(self) -> None:
        thinking = ClientVal(True)
        switch = Switch(checked=thinking, disabled=~thinking)
        copied = switch.model_copy()
        assert copied.checked is thinking
        assert copied.disabled is switch.disabled

    def test_non_expr_garbage_still_rejected(self) -> None:
        # 'yes'/'no' 等 lax bool 字符串仍会被 bool 分支吸收(M0 既有语义);非法值才报错
        with pytest.raises(ValidationError):
            Switch(checked='xyz')  # pyright: ignore[reportArgumentType]

    def test_extra_forbid_unaffected(self) -> None:
        # 自定义 __init__ 使未知 kwarg 在 Python 层即 TypeError(M0 既有语义)
        with pytest.raises(TypeError):
            Switch(nonexistent=True)  # pyright: ignore[reportCallIssue]
