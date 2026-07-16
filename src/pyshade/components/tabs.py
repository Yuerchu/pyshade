from typing import Annotated, Any, ClassVar

from pydantic import Field

from pyshade.components.base import Component, ControlledMixin, EventSpec, Handler
from pyshade.expr import ClientVal, Expr
from pyshade.state import ServerRef


class TabItem(Component):
    """Tabs 的槽子容器:label 进 TabsTrigger,children 进 TabsContent。

    value 缺省取 label;只能作为 Tabs 的直接子组件(编译期 G 规则)。
    """

    _shade_tag = 'TabItem'
    _const_props = frozenset({'value'})  # 编译期用作 radix value/去重键,从不发 rt.ov

    label: str = Field(default='', description="Tab trigger label shown in the tab list.")
    value: str = Field(default='', description="Stable item identity for tab selection; defaults to the label.")
    children: list[Component] = Field(default=[], description="Components rendered inside the tab content.")

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

    value: str | ClientVal[str] = Field(
        default='',
        description="Active tab value; bind a ClientVal for controlled state, plain empty string means uncontrolled.",
    )
    children: list[Component] = Field(default=[], description="TabItem children (enforced at compile time).")
    on_change: Annotated[
        Handler | None,
        EventSpec('change'),
        Field(description="Change handler; fires when the active tab changes."),
    ] = None

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
