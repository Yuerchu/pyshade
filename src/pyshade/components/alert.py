from typing import Any

from pyshade.components.base import Component
from pyshade.components.enums import AlertVariant
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Alert(Component):
    """shadcn Alert:置于内容流内的提示块(非浮层)。"""

    _shade_tag = 'Alert'

    title: str | Expr[str] | ServerRef[str] = ''
    description: str | None = None
    variant: AlertVariant = AlertVariant.DEFAULT

    def __init__(
        self,
        title: str | Expr[str] | ServerRef[str] = '',
        *,
        description: str | None = None,
        variant: AlertVariant = AlertVariant.DEFAULT,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'title': title, 'description': description, 'variant': variant, 'visible': visible}
        super().__init__(**data)
