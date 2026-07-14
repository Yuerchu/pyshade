from typing import Annotated, Any, ClassVar

from pyshade.components.base import Component, ControlledMixin, EventSpec, Handler
from pyshade.expr import ClientVal, Expr
from pyshade.state import ServerRef


class Switch(Component, ControlledMixin[bool]):
    """shadcn Switch;切换是离散显式操作,每次都回传合法。

    checked 绑定 ClientVal[bool] 时该 ClientVal 获得唯一写者(共用 useState)。
    """

    _shade_tag = 'Switch'
    _controlled_prop: ClassVar[str] = 'checked'

    label: str | None = None
    checked: bool | ClientVal[bool] = False
    disabled: bool | Expr[bool] | ServerRef[bool] = False
    on_change: Annotated[Handler | None, EventSpec('change')] = None

    def __init__(
        self,
        *,
        label: str | None = None,
        checked: bool | ClientVal[bool] = False,
        disabled: bool | Expr[bool] | ServerRef[bool] = False,
        on_change: Handler | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'label': label,
            'checked': checked,
            'disabled': disabled,
            'on_change': on_change,
            'visible': visible,
        }
        super().__init__(**data)
