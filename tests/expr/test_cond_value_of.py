"""cond() 类型收窄逃生舱与 value_of() 受控组件表达式源。"""

from typing import Any

import pytest

from pyshade.components import Input, PasswordInput, Switch, Text
from pyshade.expr import ClientVal, Expr, ExprType, LiteralNode, PropRef, cond, value_of


class TestCond:
    def test_passthrough_for_bool_expr(self) -> None:
        a = ClientVal(True)
        expr = ~a
        assert cond(expr) is expr

    def test_literal_left_comparison_renarrowed(self) -> None:
        # `True == expr` 运行期经反射得到 Expr,但 pyright 推成 bool;cond() 收窄回 Expr[bool]
        a = ClientVal(True)
        raw = True == a  # noqa: E712
        narrowed = cond(raw)
        assert isinstance(narrowed, Expr)
        assert narrowed is raw

    def test_plain_bool_wrapped(self) -> None:
        assert isinstance(cond(True), LiteralNode)

    def test_non_bool_expr_rejected(self) -> None:
        name = ClientVal('x')
        with pytest.raises(TypeError, match='bool'):
            cond(name)  # pyright: ignore[reportArgumentType]


class TestValueOf:
    def test_switch_yields_bool_ref(self) -> None:
        switch = Switch(label='思考模式')
        ref = value_of(switch)
        assert isinstance(ref, PropRef)
        assert ref.type is ExprType.BOOL
        assert ref.prop == 'checked'

    def test_input_yields_str_ref(self) -> None:
        field = Input(label='昵称')
        ref = value_of(field)
        assert isinstance(ref, PropRef)
        assert ref.type is ExprType.STR
        assert ref.prop == 'value'

    def test_bound_component_type_from_client_val(self) -> None:
        nick = ClientVal('')
        field = Input(value=nick)
        ref = value_of(field)
        assert ref.type is ExprType.STR

    def test_password_input_rejected(self) -> None:
        # §3.8:敏感组件双层拒绝——类型层不混入 ControlledMixin,运行时给专门错误
        password = PasswordInput(label='密码')
        with pytest.raises(TypeError, match='敏感'):
            value_of(password)  # pyright: ignore[reportArgumentType]

    def test_non_controlled_component_rejected(self) -> None:
        text = Text('hi')
        with pytest.raises(TypeError, match='受控'):
            value_of(text)  # pyright: ignore[reportArgumentType]

    def test_evaluate_falls_back_to_current_value(self) -> None:
        field = Input(value='初始值')
        assert value_of(field).evaluate() == '初始值'

    def test_evaluate_recurses_into_bound_client_val(self) -> None:
        nick = ClientVal('默认昵称')
        field = Input(value=nick)
        ref = value_of(field)
        assert ref.evaluate() == '默认昵称'
        snapshot: dict[Expr[Any], object] = {nick: '快照值'}
        assert ref.evaluate(snapshot) == '快照值'

    def test_usable_in_composite(self) -> None:
        field = Input(label='昵称', value='abc')
        expr = (value_of(field) != '') & ClientVal(True)
        assert expr.evaluate() is True
