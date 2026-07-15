from typing import Any

from pyshade.components.base import Component
from pyshade.components.enums import TooltipSide
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Tooltip(Component):
    """shadcn Tooltip:悬浮提示,wrapper 容器形态(children 恰一个宿主组件)。

    asChild 要求恰一个元素:宿主组件的 visible 必须保持默认 True
    (显隐控制请放到 Tooltip 本身的 visible 上),编译期 G 规则把关。
    open 归 radix hover 语义管理,M2 不暴露。
    """

    _shade_tag = 'Tooltip'

    text: str | Expr[str] | ServerRef[str] = ''
    side: TooltipSide = TooltipSide.TOP
    children: list[Component] = []

    def __init__(
        self,
        child: Component,
        *,
        text: str | Expr[str] | ServerRef[str],
        side: TooltipSide = TooltipSide.TOP,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'children': [child], 'text': text, 'side': side, 'visible': visible}
        super().__init__(**data)
