from typing import Annotated, Any, ClassVar

from pyshade.components.base import Component, ControlledMixin, EventSpec, Handler
from pyshade.expr import ClientVal, Expr
from pyshade.state import ServerRef


class Slider(Component, ControlledMixin[float]):
    """shadcn Slider:数值滑杆。

    0-keystroke-IPC 哲学延续:拖动(onValueChange)只更新前端本地 state,
    松手(onValueCommit)才触发 on_change 跨界回传。
    """

    _shade_tag = 'Slider'
    _controlled_prop: ClassVar[str] = 'value'

    label: str | None = None
    value: int | float | ClientVal[int] | ClientVal[float] = 0
    min: int | float = 0
    max: int | float = 100
    step: int | float = 1
    disabled: bool | Expr[bool] | ServerRef[bool] = False
    on_change: Annotated[Handler | None, EventSpec('change')] = None

    def __init__(
        self,
        *,
        label: str | None = None,
        value: int | float | ClientVal[int] | ClientVal[float] = 0,
        min: int | float = 0,  # noqa: A002 - 与 shadcn/radix prop 命名对齐
        max: int | float = 100,  # noqa: A002
        step: int | float = 1,
        disabled: bool | Expr[bool] | ServerRef[bool] = False,
        on_change: Handler | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'label': label,
            'value': value,
            'min': min,
            'max': max,
            'step': step,
            'disabled': disabled,
            'on_change': on_change,
            'visible': visible,
        }
        super().__init__(**data)
