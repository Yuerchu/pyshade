from typing import Any

from pyshade.components.base import Component
from pyshade.components.enums import Orientation
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Separator(Component):
    """shadcn Separator:分隔线。"""

    _shade_tag = 'Separator'

    orientation: Orientation = Orientation.HORIZONTAL

    def __init__(
        self,
        *,
        orientation: Orientation = Orientation.HORIZONTAL,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'orientation': orientation, 'visible': visible}
        super().__init__(**data)
