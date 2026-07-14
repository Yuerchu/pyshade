"""Page 的 ClientVal 收集与 Update 所有权拒绝(design.md §3.4 所有权公理)。"""

import pytest

from pyshade.components import Input, Switch, Text
from pyshade.events import Update
from pyshade.expr import ClientVal, read_owner
from pyshade.page import LayoutError, Page


class TestClientValCollection:
    def test_owner_engraved_and_collected(self) -> None:
        class ChatPage(Page):
            thinking = ClientVal(True)
            switch = Switch(label='思考模式', checked=thinking)

        assert read_owner(ChatPage.thinking) == 'ChatPage.thinking'
        assert ChatPage.__shade_client_vals__ == {'thinking': ChatPage.thinking}

    def test_cross_page_reuse_rejected(self) -> None:
        shared = ClientVal(False)

        class PageA(Page):
            flag = shared

        with pytest.raises(LayoutError, match='不可跨页面复用'):

            class PageB(Page):
                flag = shared

    def test_same_instance_alias_rejected(self) -> None:
        val = ClientVal(True)
        with pytest.raises(LayoutError, match='同一 ClientVal 实例'):

            class BadPage(Page):
                first = val
                second = val

    def test_page_without_client_vals_has_empty_dict(self) -> None:
        class PlainPage(Page):
            heading = Text('hi')

        assert PlainPage.__shade_client_vals__ == {}


class TestUpdateOwnership:
    def test_update_to_expr_bound_prop_rejected(self) -> None:
        class SettingsPage(Page):
            thinking = ClientVal(True)
            effort = Input(label='思考力度', disabled=~thinking)

        with pytest.raises(ValueError, match='所有权在客户端'):
            Update(SettingsPage.effort, disabled=True)

    def test_update_to_client_bind_prop_rejected(self) -> None:
        class TogglePage(Page):
            thinking = ClientVal(True)
            switch = Switch(label='思考模式', checked=thinking)

        with pytest.raises(ValueError, match='所有权在客户端'):
            Update(TogglePage.switch, checked=False)

    def test_update_to_plain_prop_still_works(self) -> None:
        class MixedPage(Page):
            thinking = ClientVal(True)
            effort = Input(label='思考力度', disabled=~thinking)

        update = Update(MixedPage.effort, label='新标签')
        assert update.to_payload() == {'target': 'MixedPage.effort', 'props': {'label': '新标签'}}
