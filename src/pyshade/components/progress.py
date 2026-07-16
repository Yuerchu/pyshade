from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Progress(Component):
    """shadcn Progress:进度条,取值 0-100;ServerRef 绑定 + 推送是主用例。"""

    _shade_tag = 'Progress'

    value: int | float | Expr[int] | Expr[float] | ServerRef[int] | ServerRef[float] = Field(
        default=0,
        description="Progress value (0-100); plain value (server-patchable), client expression, or ServerState field.",
    )

    def __init__(
        self,
        value: int | float | Expr[int] | Expr[float] | ServerRef[int] | ServerRef[float] = 0,
        *,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'value': value, 'visible': visible}
        super().__init__(**data)
