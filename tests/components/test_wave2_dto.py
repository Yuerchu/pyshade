"""M2 Wave 2 组件 DTO:Option 归一化、受控声明、Update 选项整表替换。"""

import pytest
from pydantic import ValidationError

from pyshade.components import Option, RadioGroup, Select, Slider
from pyshade.components.base import ControlledMixin, controlled_prop_of, is_sensitive
from pyshade.events import Update
from pyshade.page import Page


class TestOptionNormalization:
    def test_str_shorthand(self) -> None:
        select = Select(options=['low', 'high'])
        assert select.options == [Option(value='low', label='low'), Option(value='high', label='high')]

    def test_mixed_forms(self) -> None:
        select = Select(options=['a', Option(value='b', label='乙')])
        assert select.options[1].label == '乙'

    def test_option_frozen_and_forbid(self) -> None:
        option = Option(value='x', label='X')
        with pytest.raises(ValidationError):
            option.value = 'y'


class TestWave2Controlled:
    def test_declarations(self) -> None:
        select = Select(options=['a'])
        radio = RadioGroup(options=['a'])
        slider = Slider()
        for component, prop in ((select, 'value'), (radio, 'value'), (slider, 'value')):
            assert isinstance(component, ControlledMixin)
            assert controlled_prop_of(component) == prop
            assert is_sensitive(component) is False


class TestOptionsUpdate:
    def test_update_replaces_options_table(self) -> None:
        class PickPage(Page):
            pick = Select(options=['a', 'b'])

        update = Update(PickPage.pick, options=[Option(value='c', label='丙')])
        assert update.to_payload() == {
            'target': 'PickPage.pick',
            'props': {'options': [{'value': 'c', 'label': '丙'}]},
        }
