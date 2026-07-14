"""节点构造与构造期定型:类型推导、非法值拒绝、身份哈希、refs 收集。"""

import pytest

from pyshade.expr import ClientVal, Expr, ExprType, LiteralNode, read_owner


class TestTypeInference:
    def test_bool_before_int(self) -> None:
        # bool 是 int 子类,推导必须先判 bool
        assert LiteralNode(True).type is ExprType.BOOL
        assert LiteralNode(1).type is ExprType.INT

    def test_scalar_types(self) -> None:
        assert LiteralNode('x').type is ExprType.STR
        assert LiteralNode(1.5).type is ExprType.FLOAT

    def test_non_finite_float_rejected(self) -> None:
        with pytest.raises(TypeError, match='inf/nan'):
            LiteralNode(float('inf'))
        with pytest.raises(TypeError, match='inf/nan'):
            LiteralNode(float('nan'))

    def test_unsupported_type_rejected(self) -> None:
        # 泛型 T 静态上无约束(诚实泛型),非法标量由构造期 _infer_type 拒绝
        with pytest.raises(TypeError, match='bool/int/float/str'):
            LiteralNode(None)
        with pytest.raises(TypeError, match='bool/int/float/str'):
            ClientVal([1, 2])


class TestClientVal:
    def test_default_and_owner(self) -> None:
        val = ClientVal(True)
        assert val.default is True
        assert val.type is ExprType.BOOL
        assert read_owner(val) is None

    def test_repr_unmounted(self) -> None:
        assert '<未挂载>' in repr(ClientVal(False))


class TestIdentityHash:
    def test_usable_as_dict_key(self) -> None:
        # __eq__ 重载后 __hash__ = object.__hash__:id 派生哈希对不同对象必不同,
        # dict 探测先比完整哈希,永远不会触发 __eq__ → __bool__ 连锁
        a, b = ClientVal(True), ClientVal(True)
        table: dict[Expr[bool], str] = {a: 'a', b: 'b'}
        assert table[a] == 'a'
        assert table[b] == 'b'
        assert a in table


class TestRefs:
    def test_dedup_and_document_order(self) -> None:
        a, b = ClientVal(True), ClientVal(False)
        expr = (a & b) | ~a
        assert expr.refs() == [a, b]

    def test_literal_has_no_refs(self) -> None:
        assert LiteralNode(1).refs() == []
