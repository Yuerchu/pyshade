"""应用入口模型(design.md §5,M0 单页)。"""

from pyshade.page import Page


class ShadeApp:
    """PyShade 应用:页面集合与元数据;编译器与 EventRegistry 的共同输入。"""

    def __init__(self, *, title: str = 'PyShade App', pages: list[type[Page]]) -> None:
        if not pages:
            raise ValueError("ShadeApp 至少需要一个页面")
        self.title = title
        self.pages = pages
