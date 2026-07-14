"""运算符构造:节点形态、self-type 的运行时兜底、优先级坑双防线。

pyright 锚定:应报错的用法带 `# pyright: ignore[...]`,配合
reportUnnecessaryTypeIgnoreComment 双向锁定——静态该报的必须报,不该报的不许报。
"""

import pytest

from pyshade.expr import BoolOp, ClientVal, Compare, Concat, ExprType, LiteralNode, UnaryNot


class TestLogical:
    def test_invert_builds_unary_not(self) -> None:
        thinking = ClientVal(True)
        expr = ~thinking
        assert isinstance(expr, UnaryNot)
        assert expr.operand is thinking

    def test_and_or_build_bool_op(self) -> None:
        a, b = ClientVal(True), ClientVal(False)
        both = a & b
        either = a | b
        assert isinstance(both, BoolOp) and both.op == 'and'
        assert isinstance(either, BoolOp) and either.op == 'or'

    def test_bool_literal_operand_wrapped(self) -> None:
        a = ClientVal(True)
        expr = a & True
        assert isinstance(expr, BoolOp)
        assert isinstance(expr.right, LiteralNode)

    def test_reflected_literal_left(self) -> None:
        a = ClientVal(True)
        expr = False | a
        assert isinstance(expr, BoolOp) and expr.op == 'or'
        assert isinstance(expr.left, LiteralNode)

    def test_invert_on_str_expr_rejected(self) -> None:
        # 运行时兜底;pyright 层由 self-type 约束拒绝(锚定见 ignore 注释)
        name = ClientVal('x')
        with pytest.raises(TypeError, match='bool 表达式'):
            ~name  # pyright: ignore[reportOperatorIssue, reportUnusedExpression]

    def test_and_on_str_expr_rejected_with_paren_hint(self) -> None:
        # 优先级坑第一道防线:`a == b & c` 先算 `b & c`,b 非 bool 立即报错并提示加括号
        a, b, c = ClientVal('m'), ClientVal('n'), ClientVal('k')
        with pytest.raises(TypeError, match='括号'):
            a == b & c  # pyright: ignore[reportOperatorIssue, reportUnusedExpression]

    def test_and_non_expr_operand_rejected(self) -> None:
        a = ClientVal(True)
        with pytest.raises(TypeError, match='bool'):
            a & 'x'  # pyright: ignore[reportOperatorIssue, reportUnusedExpression]


class TestCompare:
    def test_eq_ne_build_compare(self) -> None:
        name = ClientVal('')
        eq = name == 'admin'
        ne = name != ''
        assert isinstance(eq, Compare) and eq.op == '=='
        assert isinstance(ne, Compare) and ne.op == '!='

    def test_cross_category_eq_rejected(self) -> None:
        with pytest.raises(TypeError, match='类型不一致'):
            ClientVal(True) == 'x'  # pyright: ignore[reportUnusedExpression]

    def test_numeric_interop(self) -> None:
        n = ClientVal(1)
        expr = n == 1.5
        assert isinstance(expr, Compare)

    def test_ordered_compare(self) -> None:
        n = ClientVal(0)
        s = ClientVal('a')
        assert isinstance(n < 5, Compare)
        assert isinstance(s >= 'b', Compare)

    def test_ordered_on_bool_rejected(self) -> None:
        a, b = ClientVal(True), ClientVal(False)
        with pytest.raises(TypeError, match='大小比较'):
            a < b  # pyright: ignore[reportOperatorIssue, reportUnusedExpression]

    def test_ordered_cross_category_rejected(self) -> None:
        s = ClientVal('a')
        with pytest.raises(TypeError, match='类型不一致'):
            s < 5  # pyright: ignore[reportOperatorIssue, reportUnusedExpression]

    def test_chained_comparison_raises(self) -> None:
        # 优先级坑第二道防线:链式比较触发中间结果的 __bool__
        a, b, c = ClientVal(1), ClientVal(2), ClientVal(3)
        with pytest.raises(TypeError, match='布尔上下文'):
            a < b < c  # pyright: ignore[reportUnusedExpression]


class TestAdd:
    def test_str_concat(self) -> None:
        name = ClientVal('世界')
        expr = name + '!'
        assert isinstance(expr, Concat)
        assert expr.type is ExprType.STR

    def test_str_radd_literal_left(self) -> None:
        name = ClientVal('世界')
        expr = '你好,' + name
        assert isinstance(expr, Concat)
        assert isinstance(expr.left, LiteralNode)

    def test_int_add(self) -> None:
        n = ClientVal(1)
        expr = n + 2
        assert isinstance(expr, Concat)
        assert expr.type is ExprType.INT

    def test_mixed_numeric_add_is_float(self) -> None:
        n = ClientVal(1)
        # 静态收紧到同型,运行时放行数值互通;结果类型静态不可知
        expr = n + 2.5  # pyright: ignore[reportOperatorIssue, reportUnknownVariableType]
        assert isinstance(expr, Concat)
        assert expr.type is ExprType.FLOAT

    def test_str_plus_number_rejected(self) -> None:
        name = ClientVal('x')
        with pytest.raises(TypeError, match='同为'):
            name + 1  # pyright: ignore[reportOperatorIssue, reportUnusedExpression]

    def test_bool_add_rejected(self) -> None:
        a = ClientVal(True)
        with pytest.raises(TypeError, match='同为'):
            a + True  # pyright: ignore[reportOperatorIssue, reportUnusedExpression]
