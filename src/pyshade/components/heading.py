from typing import Any, Literal

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef

HeadingLevel = Literal[1, 2, 3, 4]


class Heading(Component):
    """标题(h1-h4);text 可为普通值(Update 可 patch)、str 表达式或 ServerState 字段。

    level 决定生成的标签与排版 class,构建期定档('const',§3.3):
    运行时 patch 无法改变已生成的元素类型,故构造期即锁定。
    """

    _shade_tag = 'Heading'
    _const_props = frozenset({'level'})

    text: str | Expr[str] | ServerRef[str] = ''
    level: HeadingLevel = 2

    def __init__(
        self,
        text: str | Expr[str] | ServerRef[str] = '',
        *,
        level: HeadingLevel = 2,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'text': text, 'level': level, 'visible': visible}
        super().__init__(**data)
