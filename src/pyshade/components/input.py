from typing import Annotated, Any, ClassVar

from pyshade.components.base import Component, EventSpec, Handler


class Input(Component):
    """受控文本输入:keystroke 只更新前端本地 state,on_change 映射 DOM change 语义(blur 提交)。"""

    _shade_tag = 'Input'

    label: str | None = None
    placeholder: str | None = None
    value: str = ''
    disabled: bool = False
    on_change: Annotated[Handler | None, EventSpec('change')] = None

    def __init__(
        self,
        *,
        label: str | None = None,
        placeholder: str | None = None,
        value: str = '',
        disabled: bool = False,
        on_change: Handler | None = None,
        visible: bool = True,
    ) -> None:
        data: dict[str, Any] = {
            'label': label,
            'placeholder': placeholder,
            'value': value,
            'disabled': disabled,
            'on_change': on_change,
            'visible': visible,
        }
        super().__init__(**data)


class PasswordInput(Component):
    """敏感输入(design.md §3.8):无事件字段——类型层保证挂不了 change handler。

    前端为 uncontrolled(值不进 React state、不产生 keystroke 事件),
    仅当 submit=True 的事件触发时一次性并入 payload。
    """

    _shade_tag = 'PasswordInput'
    _sensitive: ClassVar[bool] = True

    label: str | None = None
    placeholder: str | None = None
    disabled: bool = False

    def __init__(
        self,
        *,
        label: str | None = None,
        placeholder: str | None = None,
        disabled: bool = False,
        visible: bool = True,
    ) -> None:
        data: dict[str, Any] = {'label': label, 'placeholder': placeholder, 'disabled': disabled, 'visible': visible}
        super().__init__(**data)
