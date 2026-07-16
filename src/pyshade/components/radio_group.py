from collections.abc import Sequence
from typing import Annotated, Any, ClassVar

from pydantic import Field

from pyshade.components.base import Component, ControlledMixin, EventSpec, Handler
from pyshade.components.options import Option, normalize_options
from pyshade.expr import ClientVal, Expr
from pyshade.state import ServerRef


class RadioGroup(Component, ControlledMixin[str]):
    """shadcn RadioGroup:单选组;on_change 即时回传。"""

    _shade_tag = 'RadioGroup'
    _controlled_prop: ClassVar[str] = 'value'

    label: str | None = Field(default=None, description="Optional group label.")
    options: list[Option] = Field(
        default_factory=list[Option],
        description="Selectable options; the server may replace the whole list via Update.",
    )
    value: str | ClientVal[str] = Field(
        default='',
        description="Selected option value; bind a ClientVal for client-owned controlled state.",
    )
    disabled: bool | Expr[bool] | ServerRef[bool] = Field(
        default=False,
        description="Disabled state; plain value (server-patchable), client expression, or ServerState field.",
    )
    on_change: Annotated[
        Handler | None,
        EventSpec('change'),
        Field(description="Change handler; fires immediately on selection."),
    ] = None

    def __init__(
        self,
        *,
        options: Sequence[str | Option],
        label: str | None = None,
        value: str | ClientVal[str] = '',
        disabled: bool | Expr[bool] | ServerRef[bool] = False,
        on_change: Handler | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'options': normalize_options(options),
            'label': label,
            'value': value,
            'disabled': disabled,
            'on_change': on_change,
            'visible': visible,
        }
        super().__init__(**data)
