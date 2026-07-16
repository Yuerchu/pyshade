from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.components.enums import BadgeVariant
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Badge(Component):
    """shadcn Badge:短标签展示。"""

    _shade_tag = 'Badge'

    text: str | Expr[str] | ServerRef[str] = Field(
        default='',
        description="Badge text; plain value (server-patchable), client expression, or ServerState field.",
    )
    variant: BadgeVariant = Field(default=BadgeVariant.DEFAULT, description="Visual variant (shadcn Badge variant).")

    def __init__(
        self,
        text: str | Expr[str] | ServerRef[str] = '',
        *,
        variant: BadgeVariant = BadgeVariant.DEFAULT,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'text': text, 'variant': variant, 'visible': visible}
        super().__init__(**data)
