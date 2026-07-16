from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Skeleton(Component):
    """shadcn Skeleton:加载占位;width/height 为 CSS 长度字符串(如 '8rem'、'100%')。"""

    _shade_tag = 'Skeleton'
    _const_props = frozenset({'width', 'height'})  # 编译期内联进 style,从不发 rt.ov

    width: str | None = Field(default=None, description="Width as a CSS length string (e.g. '8rem', '100%').")
    height: str | None = Field(default=None, description="Height as a CSS length string (e.g. '1rem').")

    def __init__(
        self,
        *,
        width: str | None = None,
        height: str | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'width': width, 'height': height, 'visible': visible}
        super().__init__(**data)
