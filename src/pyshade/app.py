"""应用入口模型(design.md §5)。"""

import re

from pyshade.components.base import Component
from pyshade.page import Page
from pyshade.scheme import ColorSchemeMode
from pyshade.theme import Theme

_LANG_TAG_RE = re.compile(r'^[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*$')


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
        theme: Theme | None = None,
        color_scheme: ColorSchemeMode = 'system',
        lang: str = 'en',
    ) -> None:
        if not pages:
            raise ValueError("ShadeApp 至少需要一个页面")
        if color_scheme not in ('system', 'light', 'dark'):
            raise ValueError(f"color_scheme 必须是 system/light/dark 之一(收到 {color_scheme!r})")
        if not _LANG_TAG_RE.fullmatch(lang):
            # 校验即防注入:lang 会写进 index.html 的 <html lang="..."> 属性
            raise ValueError(f"lang 必须是 BCP 47 形态的语言标签(如 'en'、'zh-CN'),收到 {lang!r}")
        self.title = title
        self.pages = pages
        self.extra_components: list[type[Component]] = list(extra_components or [])
        self.keep_alive = keep_alive
        """True → 访问过的页面保持挂载(display:none),ClientVal/受控输入跨切页存活(§3.11)。"""
        self.theme = theme
        """覆盖 :root/.dark token 的主题(theme.gen.css / bundle 内联);None 零产物。"""
        self.color_scheme = color_scheme
        """默认配色(§3.11 dark mode):system=跟随系统;localStorage 显式选择优先于此值。"""
        self.lang = lang
        """index.html 的 <html lang>(SEO/无障碍;此前硬编码导致 en 站声明 zh-CN)。"""
