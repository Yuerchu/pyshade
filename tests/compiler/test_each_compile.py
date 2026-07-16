"""M2 Phase 6 Each 编译:ChatPage golden(.map 形态)、G-E 负例、Update 拒绝、manifest。"""

import json
from typing import Any

import pytest
from pydantic import BaseModel

from pyshade.app import ShadeApp
from pyshade.compiler.checks import CompileError, check_page_ir
from pyshade.compiler.emit_app import emit_manifest
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.emit_types import collect_enums, collect_item_models, emit_types
from pyshade.compiler.ir import build_page_ir
from pyshade.components import Button, Card, Each, Input, Text
from pyshade.events import EventContext, EventRegistry, Update
from pyshade.page import Page
from pyshade.state import ServerState
from tests.compiler.test_compiler import golden_compare


class EachChatMessage(BaseModel):
    id: int
    text: str
    mine: bool = False


class EachChatState(ServerState):
    messages: list[EachChatMessage] = [EachChatMessage(id=1, text='你好')]
    tags: list[str] = ['alpha', 'beta']


def on_recall(ctx: EventContext) -> None: ...


def on_send(ctx: EventContext) -> None: ...


_TEMPLATE_NODES: dict[str, Text] = {}


def _message_template(m: Any) -> Card:
    plain = Text('对方消息', muted=True, visible=~m.mine)
    _TEMPLATE_NODES['plain'] = plain
    return Card(
        Text(m.text),
        plain,
        Button('撤回', on_click=on_recall, visible=m.mine),
        title='消息',
    )


class ChatPage(Page):
    messages = Each(EachChatState.messages, render=_message_template, key='id')
    tags = Each(EachChatState.tags, render=lambda tag: Text(tag))

    card = Card(messages, tags, title='聊天', description='M2 Phase 6')


class TestEachGolden:
    def test_chat_page_tsx(self) -> None:
        ir = build_page_ir(ChatPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # 模型项:显式 <T[]> 标注 + 指定 key
        assert 'import { Fragment } from "react";' in tsx
        assert 'import type { EachChatMessage } from "../types.gen";' in tsx
        assert (
            'rt.ov<EachChatMessage[]>("$s:EachChatState", "messages", '
            '[{"id": 1, "text": "你好", "mine": false}])'
            '.map((messagesItem: EachChatMessage, messagesIndex: number) => (' in tsx
        )
        assert '<Fragment key={messagesItem.id}>' in tsx
        # 模板 plain prop 字面量化(rt.ov 不可达);expr 走项字段
        assert '<CardTitle>{"消息"}</CardTitle>' in tsx
        assert '{(!messagesItem.mine) && (' in tsx
        # 模板事件:共享 handlerId + item_index/item_key payload
        assert (
            'onClick={() => rt.fire("ChatPage.messages.$t[0][2].on_click", '
            '{ item_index: messagesIndex, item_key: messagesItem.id })}' in tsx
        )
        # 标量项:key 回落索引
        assert 'rt.ov<string[]>("$s:EachChatState", "tags", ["alpha", "beta"])' in tsx
        assert '<Fragment key={tagsIndex}>' in tsx
        assert '<p>{tagsItem}</p>' in tsx
        golden_compare('ChatPage.gen.tsx', tsx)

    def test_types_gen_interface(self) -> None:
        ir = build_page_ir(ChatPage)
        ts = emit_types(collect_enums([ir]), collect_item_models([ir]))
        assert 'export interface EachChatMessage {' in ts
        assert 'id: number;' in ts
        assert 'text: string;' in ts
        assert 'mine: boolean;' in ts

    def test_manifest_lists_template_handler(self) -> None:
        data = json.loads(emit_manifest([build_page_ir(ChatPage)]))
        assert 'ChatPage.messages.$t[0][2].on_click' in data['pages']['ChatPage']

    def test_registry_registers_template_handler(self) -> None:
        registry = EventRegistry.from_app(ShadeApp(pages=[ChatPage]))
        entry = registry['ChatPage.messages.$t[0][2].on_click']
        assert entry.handler is on_recall


class TestOwnership:
    def test_update_rejects_template_anchor(self) -> None:
        with pytest.raises(ValueError, match='构建期常量'):
            Update(_TEMPLATE_NODES['plain'], text='改一下')


class TestEachChecks:
    def test_template_whitelist(self) -> None:
        class BadTemplatePage(Page):
            lst = Each(EachChatState.messages, render=lambda m: Card(Input(label='昵称')))

        with pytest.raises(CompileError, match='不能出现在 Each 模板内'):
            check_page_ir(build_page_ir(BadTemplatePage))

    def test_nested_each_rejected(self) -> None:
        class NestedEachPage(Page):
            lst = Each(
                EachChatState.messages,
                render=lambda m: Card(Each(EachChatState.tags, render=lambda tag: Text(tag))),
            )

        with pytest.raises(CompileError, match='不支持嵌套'):
            check_page_ir(build_page_ir(NestedEachPage))

    def test_item_ref_escape_rejected(self) -> None:
        leaked: list[Any] = []

        def render(m: Any) -> Text:
            leaked.append(m.text)
            return Text(m.text)

        class LeakPage(Page):
            lst = Each(EachChatState.messages, render=render)
            outside = Text(leaked[0])

        with pytest.raises(CompileError, match='逃逸'):
            check_page_ir(build_page_ir(LeakPage))

    def test_template_submit_rejected(self) -> None:
        class SubmitTemplatePage(Page):
            lst = Each(
                EachChatState.messages,
                render=lambda m: Button('发送', submit=True, on_click=on_send),
            )

        with pytest.raises(CompileError, match='不支持 submit=True'):
            check_page_ir(build_page_ir(SubmitTemplatePage))

    def test_template_plain_visible_false_rejected(self) -> None:
        class HiddenTemplatePage(Page):
            lst = Each(EachChatState.messages, render=lambda m: Text('隐藏', visible=False))

        with pytest.raises(CompileError, match='恒 False 无意义'):
            check_page_ir(build_page_ir(HiddenTemplatePage))

    def test_each_plain_visible_false_guards_list(self) -> None:
        # 模板外的 Each 自身 plain visible=False:发 guard,服务端 Update 可翻转
        class HiddenListPage(Page):
            tags = Each(EachChatState.tags, render=lambda tag: Text(tag), visible=False)

        ir = build_page_ir(HiddenListPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        assert '"visible", false) && rt.ov<string[]>' in tsx
