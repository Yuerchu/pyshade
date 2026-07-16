from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Card(Component):
    """容器组件:编译为 shadcn Card+CardHeader+CardTitle+CardDescription+CardContent 组合。

    children 以 positional 传入,引用先声明的页面字段(计划 Part B 布局规则)。
    """

    _shade_tag = 'Card'

    title: str | None = Field(default=None, description="Optional card title rendered in the header.")
    description: str | None = Field(default=None, description="Optional card description rendered under the title.")
    children: list[Component] = Field(
        default_factory=list[Component],
        description="Child components rendered inside the card content.",
    )

    def __init__(
        self,
        *children: Component,
        title: str | None = None,
        description: str | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'children': list(children),
            'title': title,
            'description': description,
            'visible': visible,
        }
        super().__init__(**data)
