"""nav 模块(M2 Phase 5):navigate/Navigate 防误用、注册表跳过、匿名告警豁免。"""

import warnings
from typing import Any, cast

import pytest

from pyshade.app import ShadeApp
from pyshade.components import Button, Card, Text
from pyshade.events import EventRegistry
from pyshade.nav import Navigate, NavigateAction, navigate
from pyshade.page import Page


class NavUnitDetailPage(Page):
    info = Text('详情')
    back = Button('返回', on_click=navigate('NavUnitHomePage'))


class NavUnitHomePage(Page):
    goto = Button('详情', on_click=navigate(NavUnitDetailPage))


class TestNavigateAction:
    def test_page_class_target(self) -> None:
        action = navigate(NavUnitDetailPage)
        assert isinstance(action, NavigateAction)
        assert action.page_name == 'NavUnitDetailPage'

    def test_string_target(self) -> None:
        assert navigate('NavUnitHomePage').page_name == 'NavUnitHomePage'

    def test_invalid_target_rejected(self) -> None:
        with pytest.raises(TypeError, match='Page 子类'):
            navigate(cast('Any', 123))
        with pytest.raises(TypeError, match='Page 子类'):
            navigate(cast('Any', str))
        with pytest.raises(TypeError, match='空字符串'):
            navigate('')

    def test_bool_raises(self) -> None:
        action = navigate(NavUnitDetailPage)
        with pytest.raises(TypeError, match='条件判断'):
            bool(action)

    def test_call_raises(self) -> None:
        action = navigate(NavUnitDetailPage)
        with pytest.raises(TypeError, match='不是 handler'):
            action()

    def test_component_stores_action(self) -> None:
        action = navigate(NavUnitDetailPage)
        button = Button('x', on_click=action)
        assert button.on_click is action


class TestServerNavigate:
    def test_page_name(self) -> None:
        assert Navigate(NavUnitDetailPage).page_name == 'NavUnitDetailPage'
        assert Navigate('NavUnitHomePage').page_name == 'NavUnitHomePage'

    def test_invalid_target_rejected(self) -> None:
        with pytest.raises(TypeError, match='Page 子类'):
            Navigate(cast('Any', 42))

    def test_to_payload(self) -> None:
        assert Navigate(NavUnitDetailPage).to_payload() == {
            'target': '$nav',
            'props': {'page': 'NavUnitDetailPage'},
        }


class TestRegistry:
    def test_navigate_not_registered(self) -> None:
        app = ShadeApp(pages=[NavUnitHomePage, NavUnitDetailPage])
        registry = EventRegistry.from_app(app)
        assert 'NavUnitHomePage.goto.on_click' not in registry
        assert 'NavUnitDetailPage.back.on_click' not in registry
        assert registry.page_names == frozenset({'NavUnitHomePage', 'NavUnitDetailPage'})

    def test_manual_registry_has_no_page_names(self) -> None:
        registry = EventRegistry({})
        assert registry.page_names == frozenset()


class TestLayout:
    def test_anonymous_navigate_button_no_drift_warning(self) -> None:
        """navigate 无 handlerId,匿名组件的 handlerId 漂移告警不适用。"""
        with warnings.catch_warnings():
            warnings.simplefilter('error')

            class AnonNavPage(Page):
                card = Card(Button('详情', on_click=navigate(NavUnitDetailPage)), title='T')
