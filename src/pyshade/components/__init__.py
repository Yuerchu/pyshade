"""组件 DTO 层(design.md §3.5)。

shadcn 元素的 Pydantic 基类与子类;枚举用 (str, Enum) 定义,编译期同源生成 TS union。
"""

from pyshade.components.base import Component, EventSpec, Handler
from pyshade.components.button import Button
from pyshade.components.card import Card
from pyshade.components.enums import ButtonSize, ButtonVariant
from pyshade.components.input import Input, PasswordInput
from pyshade.components.switch import Switch
from pyshade.components.text import Text

__all__ = [
    'Button',
    'ButtonSize',
    'ButtonVariant',
    'Card',
    'Component',
    'EventSpec',
    'Handler',
    'Input',
    'PasswordInput',
    'Switch',
    'Text',
]
