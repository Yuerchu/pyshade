from typing import Any

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class CodeBlock(Component):
    """代码块(编译期经 pygments 高亮成静态 HTML,需 `pyshade[content]`)。

    code/language 是构建期常量('const',§3.3);未知 language 编译期报错
    (编译路线精神:错误即暴露),纯文本用默认 'text'。
    """

    _shade_tag = 'CodeBlock'
    _const_props = frozenset({'code', 'language'})

    code: str
    language: str = 'text'

    def __init__(
        self,
        code: str,
        *,
        language: str = 'text',
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'code': code, 'language': language, 'visible': visible}
        super().__init__(**data)
