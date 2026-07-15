"""组件 DTO 层(design.md §3.5)。

shadcn 元素的 Pydantic 基类与子类;枚举用 (str, Enum) 定义,编译期同源生成 TS union。
"""

from pyshade.components.alert import Alert
from pyshade.components.badge import Badge
from pyshade.components.base import Component, EventSpec, Handler
from pyshade.components.button import Button
from pyshade.components.card import Card
from pyshade.components.checkbox import Checkbox
from pyshade.components.enums import (
    AlertVariant,
    BadgeVariant,
    ButtonSize,
    ButtonVariant,
    Orientation,
    TooltipSide,
)
from pyshade.components.input import Input, PasswordInput
from pyshade.components.progress import Progress
from pyshade.components.separator import Separator
from pyshade.components.skeleton import Skeleton
from pyshade.components.switch import Switch
from pyshade.components.text import Text
from pyshade.components.textarea import Textarea

__all__ = [
    'Alert',
    'AlertVariant',
    'Badge',
    'BadgeVariant',
    'Button',
    'ButtonSize',
    'ButtonVariant',
    'Card',
    'Checkbox',
    'Component',
    'EventSpec',
    'Handler',
    'Input',
    'Orientation',
    'PasswordInput',
    'Progress',
    'Separator',
    'Skeleton',
    'Switch',
    'Text',
    'Textarea',
    'TooltipSide',
]
