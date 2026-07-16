"""配色方案切换(M4 dark mode,design.md §3.11):color scheme 归客户端所有。

与 route 同类的纯呈现态:零 IPC、服务端不可 patch。切换机制是 class 策略
(documentElement 的 `.dark`),localStorage 只存显式选择('system' 清键回到跟随系统)。
框架不内置 ThemeToggle 组件——切换器 = `Button('切换', on_click=toggle_color_scheme())`。
"""

from typing import Literal

from pyshade.actions import ClientAction

ColorSchemeMode = Literal['system', 'light', 'dark']

_VALID_MODES = ('system', 'light', 'dark', 'toggle')


class SetColorSchemeAction(ClientAction):
    """set_color_scheme()/toggle_color_scheme() 的返回值:事件 prop 上的配色切换标记。"""

    __slots__ = ('mode',)

    def __init__(self, mode: str) -> None:
        if mode not in _VALID_MODES:
            raise TypeError(f"set_color_scheme() 的目标必须是 {'/'.join(_VALID_MODES)} 之一(收到 {mode!r})")
        self.mode = mode

    def __repr__(self) -> str:
        return f'set_color_scheme({self.mode})'


def set_color_scheme(mode: ColorSchemeMode) -> SetColorSchemeAction:
    """声明配色切换:`Button('暗色', on_click=set_color_scheme('dark'))`;'system' 清除显式选择。"""
    return SetColorSchemeAction(mode)


def toggle_color_scheme() -> SetColorSchemeAction:
    """声明明暗互切:按当前解析结果取反并落为显式选择(持久化到 localStorage)。"""
    return SetColorSchemeAction('toggle')
