from typing import Any

from pydantic import field_validator

from pyshade.components.base import Component
from pyshade.expr import Expr
from pyshade.state import ServerRef

_ALLOWED_SCHEMES = ('https://', 'http://', 'mailto:')


class Link(Component):
    """外部链接(<a> 浏览器语义);text/href 是构建期常量('const',§3.3)。

    页面间跳转请用 navigate(Page)(§3.11),不要用 Link 指向应用内页面;
    href 仅接受 http(s)/mailto,构造期校验。桌面 WebView 上外链应转系统
    浏览器打开(§6 开放问题,M4 未解)。
    """

    _shade_tag = 'Link'
    _const_props = frozenset({'text', 'href'})

    text: str
    href: str

    def __init__(
        self,
        text: str,
        href: str,
        *,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        data: dict[str, Any] = {'text': text, 'href': href, 'visible': visible}
        super().__init__(**data)

    @field_validator('href')
    @classmethod
    def _check_href(cls, value: str) -> str:
        if not value.startswith(_ALLOWED_SCHEMES):
            allowed = ' / '.join(_ALLOWED_SCHEMES)
            raise ValueError(f"href 仅接受 {allowed} 开头的外部地址(收到 {value!r});应用内跳转请用 navigate(Page)")
        return value
