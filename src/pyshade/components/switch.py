from typing import Annotated, Any

from pyshade.components.base import Component, EventSpec, Handler


class Switch(Component):
    """shadcn Switch;切换是离散显式操作,每次都回传合法。"""

    _shade_tag = 'Switch'

    label: str | None = None
    checked: bool = False
    disabled: bool = False
    on_change: Annotated[Handler | None, EventSpec('change')] = None

    def __init__(
        self,
        *,
        label: str | None = None,
        checked: bool = False,
        disabled: bool = False,
        on_change: Handler | None = None,
        visible: bool = True,
    ) -> None:
        data: dict[str, Any] = {
            'label': label,
            'checked': checked,
            'disabled': disabled,
            'on_change': on_change,
            'visible': visible,
        }
        super().__init__(**data)
