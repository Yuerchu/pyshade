from typing import Annotated, Any, ClassVar

from pyshade.components.base import Component, ControlledMixin, EventSpec, Handler
from pyshade.expr import ClientVal, Expr
from pyshade.state import ServerRef


class TabItem(Component):
    """Tabs 的槽子容器:label 进 TabsTrigger,children 进 TabsContent。

    value 缺省取 label;只能作为 Tabs 的直接子组件(编译期 G 规则)。
    """

    _shade_tag = 'TabItem'

    label: str = ''
    value: str = ''
    children: list[Component] = []

    def __init__(
        self,
        label: str,
        *children: Component,
        value: str | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'label': label,
            'value': value if value is not None else label,
            'children': list(children),
            'visible': visible,
        }
        super().__init__(**data)


class Tabs(Component, ControlledMixin[str]):
    """shadcn Tabs:children 全为 TabItem。

    value 归客户端:ClientVal 绑定 → 受控;plain 空串 → 非受控,defaultValue 取首个 item。
    """

    _shade_tag = 'Tabs'
    _controlled_prop: ClassVar[str] = 'value'

    value: str | ClientVal[str] = ''
    children: list[Component] = []
    on_change: Annotated[Handler | None, EventSpec('change')] = None

    def __init__(
        self,
        *children: Component,
        value: str | ClientVal[str] = '',
        on_change: Handler | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'children': list(children),
            'value': value,
            'on_change': on_change,
            'visible': visible,
        }
        super().__init__(**data)
