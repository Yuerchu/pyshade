from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.expr import Expr


class Card(Component):
    """容器组件:编译为 shadcn Card+CardHeader+CardTitle+CardDescription+CardContent 组合。

    children 以 positional 传入,引用先声明的页面字段(计划 Part B 布局规则)。
    """

    _shade_tag = 'Card'

    title: str | None = None
    description: str | None = None
    children: list[Component] = Field(default_factory=list[Component])

    def __init__(
        self,
        *children: Component,
        title: str | None = None,
        description: str | None = None,
        visible: bool | Expr[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'children': list(children),
            'title': title,
            'description': description,
            'visible': visible,
        }
        super().__init__(**data)
