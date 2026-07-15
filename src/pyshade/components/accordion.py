from typing import Any

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class AccordionItem(Component):
    """Accordion 的槽子容器:title 进 AccordionTrigger,children 进 AccordionContent。

    value 缺省取 title;只能作为 Accordion 的直接子组件(编译期 G 规则)。
    """

    _shade_tag = 'AccordionItem'

    title: str | Expr[str] | ServerRef[str] = ''
    value: str = ''
    children: list[Component] = []

    def __init__(
        self,
        title: str | Expr[str] | ServerRef[str],
        *children: Component,
        value: str | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        resolved = value if value is not None else (title if isinstance(title, str) else '')
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

    multiple: bool = False
    children: list[Component] = []

    def __init__(
        self,
        *children: Component,
        multiple: bool = False,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'children': list(children), 'multiple': multiple, 'visible': visible}
        super().__init__(**data)
