from typing import Any

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Text(Component):
    """纯文本显示;text 可为普通值(Update 可 patch)、str 表达式或 ServerState 字段。"""

    _shade_tag = 'Text'

    text: str | Expr[str] | ServerRef[str] = ''
    muted: bool = False

    def __init__(
        self,
        text: str | Expr[str] | ServerRef[str] = '',
        *,
        muted: bool = False,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'text': text, 'muted': muted, 'visible': visible}
        super().__init__(**data)
