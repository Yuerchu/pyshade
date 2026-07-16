"""配色 action 单测(M4 dark mode):构造校验、误用防线、组件存储、ShadeApp 参数。"""

from typing import Any, cast

import pytest

from pyshade.actions import ClientAction
from pyshade.app import ShadeApp
from pyshade.components import Button, Text
from pyshade.page import Page
from pyshade.scheme import SetColorSchemeAction, set_color_scheme, toggle_color_scheme


class SchemeUnitPage(Page):
    hello = Text('scheme')


class TestSetColorScheme:
    def test_modes(self) -> None:
        assert set_color_scheme('dark').mode == 'dark'
        assert set_color_scheme('light').mode == 'light'
        assert set_color_scheme('system').mode == 'system'
        assert toggle_color_scheme().mode == 'toggle'

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(TypeError, match='system/light/dark/toggle'):
            SetColorSchemeAction('auto')
        with pytest.raises(TypeError, match='system/light/dark/toggle'):
            set_color_scheme(cast('Any', 'toggle-me'))

    def test_is_client_action(self) -> None:
        assert isinstance(toggle_color_scheme(), ClientAction)

    def test_bool_raises(self) -> None:
        with pytest.raises(TypeError, match='条件判断'):
            bool(toggle_color_scheme())

    def test_call_raises(self) -> None:
        with pytest.raises(TypeError, match='不是 handler'):
            toggle_color_scheme()()

    def test_component_stores_action(self) -> None:
        button = Button('切换', on_click=toggle_color_scheme())
        assert isinstance(button.on_click, SetColorSchemeAction)
        assert button.on_click.mode == 'toggle'

    def test_repr(self) -> None:
        assert repr(set_color_scheme('dark')) == 'set_color_scheme(dark)'


class TestShadeAppColorScheme:
    def test_default_system(self) -> None:
        assert ShadeApp(pages=[SchemeUnitPage]).color_scheme == 'system'

    def test_explicit_value(self) -> None:
        assert ShadeApp(pages=[SchemeUnitPage], color_scheme='dark').color_scheme == 'dark'

    def test_invalid_rejected(self) -> None:
        with pytest.raises(ValueError, match='system/light/dark'):
            ShadeApp(pages=[SchemeUnitPage], color_scheme=cast('Any', 'auto'))
