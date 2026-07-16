"""页面 chrome 工厂:每页新建导航实例(组件单父规则,实例不可跨页复用)。

语言切换是构建期 Link(绝对 URL,base 来自 PYSHADE_DOCS_BASE_URL):
Link.href 是 const,不能保留当前 hash——切语言落到另一 locale 首页,v1 接受。
"""

import os
from typing import Any

from docs_site.i18n import Locale, other_locale, t
from pyshade.components import Button, ButtonVariant, Link, Separator, Text
from pyshade.nav import navigate
from pyshade.scheme import toggle_color_scheme

_DEFAULT_BASE_URL = 'https://pyshade-docs.pages.dev'


def locale_url(locale: Locale) -> str:
    base = os.environ.get('PYSHADE_DOCS_BASE_URL', _DEFAULT_BASE_URL).rstrip('/')
    return f'{base}/{locale}/'


def chrome(locale: Locale, *, prefix: str = 'nav') -> dict[str, Any]:
    """返回页面命名空间片段;prefix 防与内容字段撞名。"""
    return {
        f'{prefix}_home': Button(t('nav_home', locale), variant=ButtonVariant.GHOST, on_click=navigate('HomePage')),
        f'{prefix}_components': Button(
            t('nav_components', locale), variant=ButtonVariant.GHOST, on_click=navigate('ComponentsPage')
        ),
        f'{prefix}_quickstart': Button(
            t('nav_quickstart', locale), variant=ButtonVariant.GHOST, on_click=navigate('QuickstartPage')
        ),
        f'{prefix}_scheme': Button(
            t('toggle_scheme', locale), variant=ButtonVariant.GHOST, on_click=toggle_color_scheme()
        ),
        f'{prefix}_locale': Link(t('switch_locale', locale), locale_url(other_locale(locale))),
        f'{prefix}_rule': Separator(),
    }


def mock_note(locale: Locale, *, name: str = 'backend_note') -> dict[str, Any]:
    """服务端 demo 页的诚实标注:静态站是 JS 模拟,真后端在 pyshade dev。"""
    return {name: Text(t('mock_note', locale), muted=True)}
