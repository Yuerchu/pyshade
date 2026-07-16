"""客户端导航与服务端导航(M2 Phase 5,design.md 路由决策)。

- `navigate(Page)` → NavigateAction 标记,赋给事件 prop(如 Button.on_click),
  编译为 `rt.navigate("PageName")`——零 IPC,不进 EventRegistry。
- `Navigate(Page)` → handler 返回值,编码为 `$nav` patch(patch 的保留地址,非新协议),
  前端 App 级 store 消费后切页。
- 互相导航的页面存在类体求值顺序问题(A 引用尚未定义的 B),两者都接受类名字符串,
  字符串目标由 check_app 在编译期校验,不牺牲安全性。

本模块运行时是叶子(Page 仅 TYPE_CHECKING / 函数内延迟导入),components 可安全依赖。
"""

from typing import TYPE_CHECKING, cast

from pyshade.actions import ClientAction

if TYPE_CHECKING:
    from pyshade.page import Page


def _page_name(page: 'type[Page] | str', *, owner: str) -> str:
    """校验导航目标并取页面名;目标是否在 ShadeApp.pages 中由 check_app / dispatch 把关。"""
    if isinstance(page, str):
        if not page:
            raise TypeError(f"{owner} 的目标不能是空字符串,请传 Page 子类或其类名")
        return page
    from pyshade.page import Page

    candidate = cast('object', page)  # 运行时兜底防线:无类型代码可能传任意对象
    if not (isinstance(candidate, type) and issubclass(candidate, Page)):
        raise TypeError(f"{owner} 的目标必须是 Page 子类或其类名字符串(收到 {page!r})")
    return candidate.__name__


class NavigateAction(ClientAction):
    """navigate(Page) 的返回值:事件 prop 上的客户端导航标记(不是 handler,不可调用)。

    误用防线(__bool__/__call__ 抛错)与 is_instance schema 由 ClientAction 承接。
    """

    __slots__ = ('page_name',)

    def __init__(self, page_name: str) -> None:
        self.page_name = page_name

    def __repr__(self) -> str:
        return f'navigate({self.page_name})'


def navigate(page: 'type[Page] | str') -> NavigateAction:
    """声明客户端跳转:`Button('详情', on_click=navigate(DetailPage))`。"""
    return NavigateAction(_page_name(page, owner='navigate()'))


class Navigate:
    """handler 返回值:服务端导航,`return [Navigate(SettingsPage)]`。

    dispatch 时编码为 `{'target': '$nav', 'props': {'page': ...}}`,与 Update 同批送达;
    目标不在 ShadeApp.pages 时 dispatch 报 500。
    """

    __slots__ = ('page_name',)

    def __init__(self, page: 'type[Page] | str') -> None:
        self.page_name = _page_name(page, owner='Navigate()')

    def __repr__(self) -> str:
        return f'Navigate({self.page_name})'

    def to_payload(self) -> dict[str, object]:
        return {'target': '$nav', 'props': {'page': self.page_name}}
