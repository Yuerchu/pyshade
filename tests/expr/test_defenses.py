"""防线:布尔上下文/容器协议全部抛错,错误信息必须给出正确写法。"""

import pytest

from pyshade.expr import ClientVal


class TestBoolContext:
    def test_if_raises_with_usage_hint(self) -> None:
        val = ClientVal(True)
        with pytest.raises(TypeError) as exc_info:
            if val:  # pyright: ignore[reportGeneralTypeIssues]
                pass
        message = str(exc_info.value)
        assert '&' in message and '~' in message
        assert '括号' in message
        assert 'evaluate' in message
        assert 'cond()' in message

    def test_and_keyword_raises(self) -> None:
        a, b = ClientVal(True), ClientVal(False)
        with pytest.raises(TypeError, match='布尔上下文'):
            a and b  # pyright: ignore[reportUnusedExpression]

    def test_or_keyword_raises(self) -> None:
        a, b = ClientVal(True), ClientVal(False)
        with pytest.raises(TypeError, match='布尔上下文'):
            a or b  # pyright: ignore[reportUnusedExpression]

    def test_not_keyword_raises(self) -> None:
        val = ClientVal(True)
        with pytest.raises(TypeError, match='布尔上下文'):
            not val  # pyright: ignore[reportGeneralTypeIssues, reportUnusedExpression]


class TestContainerProtocols:
    def test_len_raises(self) -> None:
        # 定义了 __len__/__iter__/__contains__(抛错防线),静态层因此视为合法调用
        name = ClientVal('x')
        with pytest.raises(TypeError, match='len'):
            len(name)

    def test_iter_raises(self) -> None:
        name = ClientVal('x')
        with pytest.raises(TypeError, match='不可迭代'):
            list(name)

    def test_contains_raises(self) -> None:
        name = ClientVal('xyz')
        with pytest.raises(TypeError, match='in'):
            'x' in name  # pyright: ignore[reportUnusedExpression]
