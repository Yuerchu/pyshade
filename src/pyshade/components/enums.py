"""组件枚举:与 shadcn cva variant 同源,编译期发射 TS union(design.md §3.5)。

用 (str, Enum) 而非 StrEnum(requires-python>=3.10,StrEnum 是 3.11+);
3.10/3.11 的 f-string 行为有差异,编译器发射一律取 `.value`。
"""

from enum import Enum


class ButtonVariant(str, Enum):
    DEFAULT = 'default'
    DESTRUCTIVE = 'destructive'
    OUTLINE = 'outline'
    SECONDARY = 'secondary'
    GHOST = 'ghost'
    LINK = 'link'


class ButtonSize(str, Enum):
    DEFAULT = 'default'
    SM = 'sm'
    LG = 'lg'
    ICON = 'icon'


class BadgeVariant(str, Enum):
    DEFAULT = 'default'
    SECONDARY = 'secondary'
    DESTRUCTIVE = 'destructive'
    OUTLINE = 'outline'


class AlertVariant(str, Enum):
    DEFAULT = 'default'
    DESTRUCTIVE = 'destructive'


class Orientation(str, Enum):
    HORIZONTAL = 'horizontal'
    VERTICAL = 'vertical'


class TooltipSide(str, Enum):
    TOP = 'top'
    RIGHT = 'right'
    BOTTOM = 'bottom'
    LEFT = 'left'
