from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class AccordionItem(Component):
    """Accordion 的槽子容器:title 进 AccordionTrigger,children 进 AccordionContent。

    value 缺省取 title;只能作为 Accordion 的直接子组件(编译期 G 规则)。
    """

    _shade_tag = 'AccordionItem'
    _const_props = frozenset({'value'})  # 编译期用作 radix value/去重键,从不发 rt.ov

    title: str | Expr[str] | ServerRef[str] = Field(
        default='',
        description="Trigger title; plain value (server-patchable), client expression, or ServerState field.",
    )
    value: str = Field(default='', description="Stable item identity for open/close state; defaults to the title.")
    children: list[Component] = Field(default=[], description="Components rendered inside the item content.")

    def __init__(
        self,
        title: str | Expr[str] | ServerRef[str],
        *children: Component,
        value: str | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        if value is None and not isinstance(title, str):
            # value 缺省取 title;非 str title 落 '' 会在编译期报"value 重复",错误指向用户没写过的东西
            raise TypeError(
                "AccordionItem 的 title 是表达式/ServerState 字段时必须显式提供 value"
                "(开合状态的稳定标识,编译期用于去重);如 AccordionItem(ChatState.faq_title, ..., value='faq-1')"
            )
        resolved = value if value is not None else title
        data: dict[str, Any] = {
            'title': title,
            'value': resolved,
            'children': list(children),
            'visible': visible,
        }
        super().__init__(**data)


class Accordion(Component):
    """shadcn Accordion:children 全为 AccordionItem;M2 不受控(开合归 radix)。"""

    _shade_tag = 'Accordion'
    _const_props = frozenset({'multiple'})  # 编译期决定 radix type="single|multiple",从不发 rt.ov

    multiple: bool = Field(default=False, description="Allow multiple items to be open at once.")
    children: list[Component] = Field(default=[], description="AccordionItem children (enforced at compile time).")

    def __init__(
        self,
        *children: Component,
        multiple: bool = False,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'children': list(children), 'multiple': multiple, 'visible': visible}
        super().__init__(**data)
