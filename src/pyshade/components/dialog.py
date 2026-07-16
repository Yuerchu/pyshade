from typing import Annotated, Any, ClassVar

from pydantic import Field

from pyshade.components.base import Component, ControlledMixin, EventSpec, Handler
from pyshade.expr import ClientVal, Expr
from pyshade.state import ServerRef


class Dialog(Component, ControlledMixin[bool]):
    """shadcn Dialog:模态弹窗。

    open 归客户端所有:ClientVal 绑定 → 受控(radix 经 onOpenChange 回写,唯一写者吻合);
    plain → defaultOpen(仅初始值,挂载后 Update 无效——已知例外,服务端弹窗记 M3)。
    不允许 ServerRef(服务端推 open 后客户端 ESC 关闭即双写者)。
    trigger 是标量组件槽(典型为 Button),radix Trigger 接管点击,不得再绑 on_click。
    """

    _shade_tag = 'Dialog'
    _controlled_prop: ClassVar[str] = 'open'

    trigger: Component | None = Field(
        default=None,
        description="Trigger slot (typically a Button); radix Trigger owns its click, do not bind on_click.",
    )
    title: str | None = Field(default=None, description="Optional dialog title.")
    description: str | None = Field(default=None, description="Optional dialog description.")
    open: bool | ClientVal[bool] = Field(
        default=False,
        description="Open state; bind a ClientVal for controlled state, plain value maps to defaultOpen only.",
    )
    children: list[Component] = Field(default=[], description="Dialog body components.")

    def __init__(
        self,
        *children: Component,
        trigger: Component | None = None,
        title: str | None = None,
        description: str | None = None,
        open: bool | ClientVal[bool] = False,  # noqa: A002 - 与 radix prop 命名对齐
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'trigger': trigger,
            'title': title,
            'description': description,
            'open': open,
            'children': list(children),
            'visible': visible,
        }
        super().__init__(**data)


class AlertDialog(Component, ControlledMixin[bool]):
    """shadcn AlertDialog:确认弹窗(结构固定,无自由 children——弹窗内表单用 Dialog+Button 组合)。

    on_confirm:点确认(radix Action 自动关闭);on_cancel:取消路径统一触发
    (ESC/遮罩/取消按钮——与 shadcn 行为的显式约定)。payload 均为 {}。
    """

    _shade_tag = 'AlertDialog'
    _controlled_prop: ClassVar[str] = 'open'

    trigger: Component | None = Field(
        default=None,
        description="Trigger slot (typically a Button); radix Trigger owns its click, do not bind on_click.",
    )
    title: str = Field(default='', description="Dialog title.")
    description: str | None = Field(default=None, description="Optional description text.")
    confirm_text: str = Field(default='确认', description="Label of the confirm button.")
    cancel_text: str = Field(default='取消', description="Label of the cancel button.")
    destructive: bool = Field(default=False, description="Render the confirm button in destructive style.")
    open: bool | ClientVal[bool] = Field(
        default=False,
        description="Open state; bind a ClientVal for controlled state, plain value maps to defaultOpen only.",
    )
    on_confirm: Annotated[
        Handler | None,
        EventSpec('click'),
        Field(description="Confirm handler; the radix Action closes the dialog automatically."),
    ] = None
    on_cancel: Annotated[
        Handler | None,
        EventSpec('click'),
        Field(description="Cancel handler; fires on every cancel path (ESC / overlay / cancel button)."),
    ] = None

    def __init__(
        self,
        title: str,
        *,
        trigger: Component | None = None,
        description: str | None = None,
        confirm_text: str = '确认',
        cancel_text: str = '取消',
        destructive: bool = False,
        open: bool | ClientVal[bool] = False,  # noqa: A002
        on_confirm: Handler | None = None,
        on_cancel: Handler | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {
            'title': title,
            'trigger': trigger,
            'description': description,
            'confirm_text': confirm_text,
            'cancel_text': cancel_text,
            'destructive': destructive,
            'open': open,
            'on_confirm': on_confirm,
            'on_cancel': on_cancel,
            'visible': visible,
        }
        super().__init__(**data)
