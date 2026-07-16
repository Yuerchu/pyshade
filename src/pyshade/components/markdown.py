from typing import Any

from pydantic import Field

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef


class Markdown(Component):
    """Markdown 长文(编译期经 mistune 渲染成静态 HTML,需 `pyshade[content]`)。

    source 是构建期常量('const',§3.3):HTML 在编译期定稿,运行时 patch 源文本
    无法触发重渲染,构造期即锁定。raw HTML 一律转义(escape=True,无逃生口);
    运行时动态 markdown(如 LLM 输出)不支持,记 §6 开放问题。
    """

    _shade_tag = 'Markdown'
    _const_props = frozenset({'source'})

    source: str = Field(
        description="Markdown source rendered to static HTML at compile time (raw HTML escaped); build-time constant.",
    )

    def __init__(
        self,
        source: str,
        *,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'source': source, 'visible': visible}
        super().__init__(**data)
