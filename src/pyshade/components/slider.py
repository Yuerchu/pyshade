from typing import Annotated, Any, ClassVar

from pydantic import Field

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

    label: str | None = Field(default=None, description="Optional label rendered above the slider.")
    value: int | float | ClientVal[int] | ClientVal[float] = Field(
        default=0,
        description="Numeric value; bind a ClientVal for client-owned controlled state (dragging stays client-side).",
    )
    min: int | float = Field(default=0, description="Minimum value.")
    max: int | float = Field(default=100, description="Maximum value.")
    step: int | float = Field(default=1, description="Step increment.")
    disabled: bool | Expr[bool] | ServerRef[bool] = Field(
        default=False,
        description="Disabled state; plain value (server-patchable), client expression, or ServerState field.",
    )
    on_change: Annotated[
        Handler | None,
        EventSpec('change'),
        Field(description="Change handler; fires on release (onValueCommit), not while dragging."),
    ] = None

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
