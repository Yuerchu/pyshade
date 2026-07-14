from typing import Any

from pyshade.components.base import Component
from pyshade.expr import Expr


class Text(Component):
    """纯文本显示;Python 回传更新 UI 的显示锚点,text 可绑定 str 表达式。"""

    _shade_tag = 'Text'

    text: str | Expr[str] = ''
    muted: bool = False

    def __init__(self, text: str | Expr[str] = '', *, muted: bool = False, visible: bool | Expr[bool] = True) -> None:
        data: dict[str, Any] = {'text': text, 'muted': muted, 'visible': visible}
        super().__init__(**data)
