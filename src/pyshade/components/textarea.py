from typing import Annotated, Any, ClassVar

from pyshade.components.base import Component, ControlledMixin, EventSpec, Handler
from pyshade.expr import ClientVal, Expr
from pyshade.state import ServerRef


class Textarea(Component, ControlledMixin[str]):
    """多行文本输入:与 Input 同语义(keystroke 仅本地 state,on_change 映射 blur 提交)。"""

    _shade_tag = 'Textarea'
    _controlled_prop: ClassVar[str] = 'value'

    label: str | None = None
    placeholder: str | None = None
    value: str | ClientVal[str] = ''
    rows: int = 3
    disabled: bool | Expr[bool] | ServerRef[bool] = False
    on_change: Annotated[Handler | None, EventSpec('change')] = None

    def __init__(
        self,
        *,
        label: str | None = None,
        placeholder: str | None = None,
        value: str | ClientVal[str] = '',
        rows: int = 3,
        disabled: bool | Expr[bool] | ServerRef[bool] = False,
        on_change: Handler | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'label': label,
            'placeholder': placeholder,
            'value': value,
            'rows': rows,
            'disabled': disabled,
            'on_change': on_change,
            'visible': visible,
        }
        super().__init__(**data)
