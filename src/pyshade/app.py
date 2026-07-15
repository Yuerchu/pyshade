"""应用入口模型(design.md §5)。"""

from pyshade.components.base import Component
from pyshade.page import Page


class ShadeApp:
    """PyShade 应用:页面集合与元数据;编译器与 EventRegistry 的共同输入。

    extra_components:按需打包的逃生舱(design.md §3.6)——组件集合按编译期 IR 收集,
    动态构造导致 IR 看不到的组件在此显式声明,entry.tsx 以 side-effect import 保住模块进图。
    """

    def __init__(
        self,
        *,
        title: str = 'PyShade App',
        pages: list[type[Page]],
        extra_components: list[type[Component]] | None = None,
        keep_alive: bool = False,
    ) -> None:
        if not pages:
            raise ValueError("ShadeApp 至少需要一个页面")
        self.title = title
        self.pages = pages
        self.extra_components: list[type[Component]] = list(extra_components or [])
        self.keep_alive = keep_alive
        """True → 访问过的页面保持挂载(display:none),ClientVal/受控输入跨切页存活(§3.11)。"""
