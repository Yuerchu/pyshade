from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class ScrollArea(Component):
    """shadcn ScrollArea:固定高度滚动容器;height 为 CSS 长度字符串。"""

    _shade_tag = 'ScrollArea'
    _const_props = frozenset({'height'})  # 编译期内联进 style,从不发 rt.ov

    height: str = Field(default='16rem', description="Fixed viewport height as a CSS length string (e.g. '16rem').")
    children: list[Component] = Field(default=[], description="Child components rendered inside the scroll viewport.")

    def __init__(
        self,
        *children: Component,
        height: str = '16rem',
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'children': list(children), 'height': height, 'visible': visible}
        super().__init__(**data)
