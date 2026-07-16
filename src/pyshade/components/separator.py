from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.components.enums import Orientation
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Separator(Component):
    """shadcn Separator:分隔线。"""

    _shade_tag = 'Separator'

    orientation: Orientation = Field(
        default=Orientation.HORIZONTAL,
        description="Separator orientation (horizontal or vertical).",
    )

    def __init__(
        self,
        *,
        orientation: Orientation = Orientation.HORIZONTAL,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'orientation': orientation, 'visible': visible}
        super().__init__(**data)
