from typing import Any, Literal

from pydantic import Field

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef

StackWidth = Literal['sm', 'md', 'lg', 'full']


class Stack(Component):
    """纵向布局容器(内容组件族,§3.13):无边框卡片语义,承载文档/长文页面流。

    width 决定内容列宽档位(sm=24rem/md=48rem/lg=64rem/full),构建期定档('const'):
    与 Heading.level 同理,运行时 patch 无法改变已生成的 class。
    """

    _shade_tag = 'Stack'
    _const_props = frozenset({'width'})

    children: list[Component] = Field(
        default_factory=list[Component],
        description="Child components laid out vertically (column flex, gap-4).",
    )
    width: StackWidth = Field(
        default='md',
        description="Content column width preset (sm/md/lg/full); build-time constant.",
    )

    def __init__(
        self,
        *children: Component,
        width: StackWidth = 'md',
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'children': list(children), 'width': width, 'visible': visible}
        super().__init__(**data)
