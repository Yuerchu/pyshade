"""组件 DTO 层(design.md §3.5)。

shadcn 元素的 Pydantic 基类与子类;枚举用 (str, Enum) 定义,编译期同源生成 TS union。
"""

from pyshade.components.accordion import Accordion, AccordionItem
from pyshade.components.alert import Alert
from pyshade.components.badge import Badge
from pyshade.components.base import Component, EventSpec, Handler
from pyshade.components.button import Button
from pyshade.components.card import Card
from pyshade.components.checkbox import Checkbox
from pyshade.components.dialog import AlertDialog, Dialog
from pyshade.components.each import Each, item_snapshot
from pyshade.components.enums import (
    AlertVariant,
    BadgeVariant,
    ButtonSize,
    ButtonVariant,
    Orientation,
    TooltipSide,
)
from pyshade.components.input import Input, PasswordInput
from pyshade.components.options import Option
from pyshade.components.progress import Progress
from pyshade.components.radio_group import RadioGroup
from pyshade.components.scroll_area import ScrollArea
from pyshade.components.select import Select
from pyshade.components.separator import Separator
from pyshade.components.skeleton import Skeleton
from pyshade.components.slider import Slider
from pyshade.components.switch import Switch
from pyshade.components.tabs import TabItem, Tabs
from pyshade.components.text import Text
from pyshade.components.textarea import Textarea
from pyshade.components.tooltip import Tooltip

__all__ = [
    'Accordion',
    'AccordionItem',
    'Alert',
    'AlertDialog',
    'AlertVariant',
    'Badge',
    'BadgeVariant',
    'Button',
    'ButtonSize',
    'ButtonVariant',
    'Card',
    'Checkbox',
    'Component',
    'Dialog',
    'Each',
    'EventSpec',
    'Handler',
    'Input',
    'item_snapshot',
    'Option',
    'Orientation',
    'PasswordInput',
    'Progress',
    'RadioGroup',
    'ScrollArea',
    'Select',
    'Separator',
    'Skeleton',
    'Slider',
    'Switch',
    'TabItem',
    'Tabs',
    'Text',
    'Textarea',
    'Tooltip',
    'TooltipSide',
]
