from typing import Annotated, Any

from pydantic import Field

from pyshade.actions import ClientAction
from pyshade.components.base import Component, EventSpec, Handler
from pyshade.components.enums import ButtonSize, ButtonVariant
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Button(Component):
    """shadcn Button;submit=True 的事件 payload 允许携带敏感输入值(design.md §3.8)。

    on_click 除 handler 外也接受零 IPC 客户端 action:navigate(Page) / set_color_scheme()。
    """

    _shade_tag = 'Button'

    text: str = Field(default='', description="Button label; plain value (server-patchable).")
    variant: ButtonVariant = Field(
        default=ButtonVariant.DEFAULT,
        description="Visual variant (shadcn Button variant).",
    )
    size: ButtonSize = Field(default=ButtonSize.DEFAULT, description="Size preset (shadcn Button size).")
    disabled: bool | Expr[bool] | ServerRef[bool] = Field(
        default=False,
        description="Disabled state; plain value (server-patchable), client expression, or ServerState field.",
    )
    submit: bool = Field(
        default=False,
        description="Submit button: event payload carries the page's named input values (incl. sensitive).",
    )
    on_click: Annotated[
        Handler | ClientAction | None,
        EventSpec('click'),
        Field(description="Click handler, or a zero-IPC client action (navigate() / set_color_scheme())."),
    ] = None

    def __init__(
        self,
        text: str = '',
        *,
        variant: ButtonVariant = ButtonVariant.DEFAULT,
        size: ButtonSize = ButtonSize.DEFAULT,
        disabled: bool | Expr[bool] | ServerRef[bool] = False,
        submit: bool = False,
        on_click: Handler | ClientAction | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'text': text,
            'variant': variant,
            'size': size,
            'disabled': disabled,
            'submit': submit,
            'on_click': on_click,
            'visible': visible,
        }
        super().__init__(**data)
