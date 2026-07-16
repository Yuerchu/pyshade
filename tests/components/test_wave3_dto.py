"""M2 Wave 3 组件 DTO:槽语义、value 缺省、受控声明、敏感标记。"""

import pytest

from pyshade.components import (
    Accordion,
    AccordionItem,
    AlertDialog,
    Button,
    Dialog,
    ScrollArea,
    TabItem,
    Tabs,
    Text,
    Tooltip,
)
from pyshade.components.base import ControlledMixin, controlled_prop_of, is_sensitive
from pyshade.page import iter_children
from pyshade.state import ServerState

WAVE3 = (Dialog, AlertDialog, Tooltip, Tabs, TabItem, Accordion, AccordionItem, ScrollArea)


class TestWave3Dto:
    def test_shade_tags_and_sensitivity(self) -> None:
        tags = {cls._shade_tag for cls in WAVE3}  # pyright: ignore[reportPrivateUsage]
        assert tags == {
            'Dialog',
            'AlertDialog',
            'Tooltip',
            'Tabs',
            'TabItem',
            'Accordion',
            'AccordionItem',
            'ScrollArea',
        }

    def test_controlled_declarations(self) -> None:
        dialog = Dialog(Text('x'))
        alert = AlertDialog('标题')
        tabs = Tabs(TabItem('a'))
        for component, prop in ((dialog, 'open'), (alert, 'open'), (tabs, 'value')):
            assert isinstance(component, ControlledMixin)
            assert controlled_prop_of(component) == prop
            assert is_sensitive(component) is False

    def test_trigger_scalar_slot_enters_children(self) -> None:
        trigger = Button('打开')
        content = Text('内容')
        dialog = Dialog(content, trigger=trigger, title='T')
        children = iter_children(dialog)
        # 标量槽按 model_fields 声明序:trigger 先于 children 列表
        assert children == [trigger, content]

    def test_tab_item_value_defaults_to_label(self) -> None:
        assert TabItem('账号').value == '账号'
        assert TabItem('账号', value='acct').value == 'acct'

    def test_accordion_item_value_defaults_to_title(self) -> None:
        assert AccordionItem('问题一').value == '问题一'
        assert AccordionItem('问题一', value='q1').value == 'q1'

    def test_accordion_item_non_str_title_requires_value(self) -> None:
        # 非 str title 落空串 value 会在编译期报"value 重复",错误指向用户没写过的东西
        class FaqState(ServerState):
            faq_title: str = '标题'

        with pytest.raises(TypeError, match='显式提供 value'):
            AccordionItem(FaqState.faq_title, Text('内容'))
        item = AccordionItem(FaqState.faq_title, Text('内容'), value='faq-1')
        assert item.value == 'faq-1'

    def test_tooltip_wraps_exactly_one_child(self) -> None:
        host = Button('宿主')
        tip = Tooltip(host, text='提示')
        assert iter_children(tip) == [host]
