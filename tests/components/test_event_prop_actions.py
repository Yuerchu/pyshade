"""事件 prop 的 ClientAction 声明防线(发版前审查):ClientAction 定义了 __call__,
会满足 `Handler | None` 的 Callable 分支——未声明 `| ClientAction` 的事件 prop 被赋
action 时编译产物中绑定会静默消失,EventSpec 的 core-schema 钩子在构造期拒绝。"""

import pytest
from pydantic import ValidationError

from pyshade.components import AlertDialog, Button, Input, Tabs
from pyshade.nav import navigate
from pyshade.scheme import set_color_scheme, toggle_color_scheme


class TestUndeclaredActionRejected:
    def test_input_on_change_navigate_rejected(self) -> None:
        with pytest.raises(ValidationError, match='客户端 action'):
            Input(on_change=navigate('SomePage'))

    def test_tabs_on_change_scheme_rejected(self) -> None:
        with pytest.raises(ValidationError, match='客户端 action'):
            Tabs(on_change=set_color_scheme('dark'))

    def test_alert_dialog_on_confirm_rejected(self) -> None:
        with pytest.raises(ValidationError, match='客户端 action'):
            AlertDialog(title='t', on_confirm=toggle_color_scheme())


class TestDeclaredActionAllowed:
    def test_button_on_click_navigate_ok(self) -> None:
        button = Button('go', on_click=navigate('SomePage'))
        assert button.on_click is not None

    def test_button_on_click_scheme_ok(self) -> None:
        button = Button('dark', on_click=toggle_color_scheme())
        assert button.on_click is not None

    def test_json_schema_still_works(self) -> None:
        # M4 的宽松占位 schema 回归锚:core-schema 钩子不得破坏 model_json_schema()
        schema = Input.model_json_schema()
        assert schema['properties']['on_change']['title'] == 'EventHandler'
