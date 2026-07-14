"""双端求值一致性:to_js 产物(经文本映射回 Python 语义)与 evaluate 在输入矩阵上逐点相等。

映射仅覆盖本子集且测试数据避开歧义字符(字符串字面量不含运算符片段),
是测试专用的极简翻译,不是 JS 求值器。
"""

import itertools
from typing import Any

import pytest

from pyshade.expr import ClientVal, Expr


def js_to_python_source(js: str) -> str:
    """`===`/`!==`/`&&`/`||`/`!`/`true`/`false` → Python 等价拼写;顺序敏感(!== 先于 !)。"""
    out = js
    out = out.replace('===', '__EQ__').replace('!==', '__NE__')
    out = out.replace('&&', ' and ').replace('||', ' or ').replace('!', ' not ')
    out = out.replace('__EQ__', '==').replace('__NE__', '!=')
    out = out.replace('true', 'True').replace('false', 'False')
    return out


def assert_dual_consistent(expr: Expr[Any], bindings: dict[str, Expr[Any]], values: dict[str, object]) -> None:
    scope: dict[Expr[Any], str] = {leaf: name for name, leaf in bindings.items()}
    snapshot: dict[Expr[Any], object] = {leaf: values[name] for name, leaf in bindings.items()}
    python_side = expr.evaluate(snapshot)
    js_side = eval(js_to_python_source(expr.to_js(scope)), {'__builtins__': {}}, dict(values))  # noqa: S307
    assert python_side == js_side, f'js={expr.to_js(scope)!r} 双端不一致: {python_side!r} vs {js_side!r}'


class TestBoolMatrix:
    @pytest.mark.parametrize('a_val', [True, False])
    @pytest.mark.parametrize('b_val', [True, False])
    @pytest.mark.parametrize('c_val', [True, False])
    def test_logical_combinations(self, a_val: bool, b_val: bool, c_val: bool) -> None:
        a, b, c = ClientVal(True), ClientVal(False), ClientVal(True)
        bindings: dict[str, Expr[Any]] = {'a': a, 'b': b, 'c': c}
        values: dict[str, object] = {'a': a_val, 'b': b_val, 'c': c_val}
        cases: list[Expr[Any]] = [
            ~a,
            a & b,
            a | b,
            (a | b) & ~c,
            ~(a & b) | (b & c),
            (a == b) | (b != c),
        ]
        for expr in cases:
            assert_dual_consistent(expr, bindings, values)


class TestStrAndNumeric:
    @pytest.mark.parametrize(
        ('name_val', 'count_val'),
        list(itertools.product(['', 'admin', 'yuerchu'], [0, 3, 10])),
    )
    def test_compare_and_concat(self, name_val: str, count_val: int) -> None:
        name = ClientVal('')
        count = ClientVal(0)
        bindings: dict[str, Expr[Any]] = {'name': name, 'count': count}
        values: dict[str, object] = {'name': name_val, 'count': count_val}
        cases: list[Expr[Any]] = [
            name == 'admin',
            name != '',
            count > 5,
            count + 1 <= 4,
            (name != '') & (count >= 3),
            name + '@yxqi.cn',
            'user:' + name,
            count + count,
        ]
        for expr in cases:
            assert_dual_consistent(expr, bindings, values)


class TestJsShape:
    """to_js 产出形态:复合子表达式一律加括号,叶子不加。"""

    def test_representative_shapes(self) -> None:
        a, b, c = ClientVal(True), ClientVal(False), ClientVal(True)
        name = ClientVal('')
        scope: dict[Expr[Any], str] = {a: 'aVal', b: 'bVal', c: 'cVal', name: 'nameVal'}
        assert (~a).to_js(scope) == '!aVal'
        assert (~(a & b)).to_js(scope) == '!(aVal && bVal)'
        assert ((a | b) & ~c).to_js(scope) == '(aVal || bVal) && (!cVal)'
        assert (a & (name == 'x')).to_js(scope) == 'aVal && (nameVal === "x")'
        assert (name != '').to_js(scope) == 'nameVal !== ""'
        assert ('你好,' + name + '!').to_js(scope) == '("你好," + nameVal) + "!"'

    def test_literal_rendering(self) -> None:
        a = ClientVal(True)
        scope: dict[Expr[Any], str] = {a: 'aVal'}
        assert (a == True).to_js(scope) == 'aVal === true'  # noqa: E712
        n = ClientVal(0.5)
        scope_n: dict[Expr[Any], str] = {n: 'n'}
        assert (n > 1.5).to_js(scope_n) == 'n > 1.5'


class TestEvaluateFallback:
    def test_client_val_falls_back_to_default(self) -> None:
        a = ClientVal(True)
        name = ClientVal('游客')
        assert (~a).evaluate() is False
        assert ('你好,' + name).evaluate() == '你好,游客'

    def test_snapshot_overrides_default(self) -> None:
        a = ClientVal(True)
        snapshot: dict[Expr[Any], object] = {a: False}
        assert (~a).evaluate(snapshot) is True

    def test_missing_scope_key_raises(self) -> None:
        a, b = ClientVal(True), ClientVal(False)
        scope: dict[Expr[Any], str] = {a: 'aVal'}
        with pytest.raises(KeyError, match='scope'):
            (a & b).to_js(scope)
