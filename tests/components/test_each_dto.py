"""Each DTO(M2 Phase 6):构造校验、模板收集、ItemProxy 定型/memoize、item_snapshot 双端对拍。"""

from typing import Any, cast

import pytest
from pydantic import BaseModel

from pyshade.components import Button, Each, Text, item_snapshot
from pyshade.components.base import read_anchor
from pyshade.expr import Expr, ExprType, ItemRef
from pyshade.page import Page, iter_children, iter_nodes
from pyshade.state import ServerState


class EachDtoMessage(BaseModel):
    id: int
    text: str
    mine: bool = False


class EachDtoState(ServerState):
    messages: list[EachDtoMessage] = [EachDtoMessage(id=1, text='你好')]
    tags: list[str] = ['alpha']
    status: str = '就绪'


class NestedModel(BaseModel):
    inner: list[int] = []


class EachDtoNestedState(ServerState):
    rows: list[NestedModel] = []


class TestConstruction:
    def test_items_must_be_server_ref(self) -> None:
        with pytest.raises(TypeError, match='ServerState 的 list 字段'):
            Each(cast('Any', [1, 2]), render=lambda item: Text('x'))

    def test_items_must_be_list_annotation(self) -> None:
        with pytest.raises(TypeError, match='list 注解'):
            Each(cast('Any', EachDtoState.status), render=lambda item: Text('x'))

    def test_item_model_must_be_flat(self) -> None:
        with pytest.raises(TypeError, match='扁平标量模型'):
            Each(EachDtoNestedState.rows, render=lambda item: Text('x'))

    def test_key_rejected_for_scalar_items(self) -> None:
        with pytest.raises(TypeError, match='标量项的 Each 不支持 key'):
            Each(EachDtoState.tags, render=lambda item: Text('x'), key='id')

    def test_key_must_be_model_field(self) -> None:
        with pytest.raises(TypeError, match="key 'nope' 不是"):
            Each(EachDtoState.messages, render=lambda m: Text('x'), key='nope')

    def test_key_must_be_str_or_int(self) -> None:
        with pytest.raises(TypeError, match='必须是 str/int'):
            Each(EachDtoState.messages, render=lambda m: Text('x'), key='mine')

    def test_render_must_return_component(self) -> None:
        with pytest.raises(TypeError, match='必须返回一个 Component'):
            Each(EachDtoState.messages, render=lambda m: cast('Any', 'not a component'))

    def test_render_must_not_reuse_anchored_component(self) -> None:
        class DonorPage(Page):
            hint = Text('已挂载')

        with pytest.raises(TypeError, match='已属于'):
            Each(EachDtoState.messages, render=lambda m: DonorPage.hint)


class TestItemProxy:
    def test_typed_refs_from_model_annotations(self) -> None:
        captured: dict[str, Expr[Any]] = {}

        def render(m: Any) -> Text:
            captured['text'] = m.text
            captured['mine'] = m.mine
            captured['id'] = m.id
            return Text(m.text)

        Each(EachDtoState.messages, render=render)
        assert isinstance(captured['text'], ItemRef)
        assert captured['text'].type is ExprType.STR
        assert captured['mine'].type is ExprType.BOOL
        assert captured['id'].type is ExprType.INT

    def test_refs_are_memoized(self) -> None:
        def render(m: Any) -> Text:
            assert m.text is m.text  # scope/snapshot 按身份哈希,同字段必须同叶子
            return Text(m.text)

        Each(EachDtoState.messages, render=render)

    def test_unknown_field_raises(self) -> None:
        def render(m: Any) -> Text:
            return Text(m.nope)

        with pytest.raises(AttributeError, match="没有字段 'nope'"):
            Each(EachDtoState.messages, render=render)

    def test_scalar_items_get_expr_directly(self) -> None:
        captured: list[Expr[Any]] = []

        def render(tag: Any) -> Text:
            captured.append(tag)
            return Text(tag)

        Each(EachDtoState.tags, render=render)
        assert isinstance(captured[0], ItemRef)
        assert captured[0].type is ExprType.STR


class TestLayoutIntegration:
    def test_template_not_in_children_but_in_iter_nodes(self) -> None:
        class EachDtoPage(Page):
            lst = Each(EachDtoState.messages, render=lambda m: Text(m.text))

        each = EachDtoPage.lst
        assert iter_children(each) == []
        nodes = list(iter_nodes(EachDtoPage))
        template = [c for c in nodes if isinstance(c, Text)]
        assert len(template) == 1
        assert read_anchor(template[0]) == 'EachDtoPage.lst.$t[0]'

    def test_template_button_handler_gets_template_anchor(self) -> None:
        def on_pick(ctx: object) -> None: ...

        class EachDtoBtnPage(Page):
            lst = Each(
                EachDtoState.messages,
                render=lambda m: Button('选择', on_click=on_pick),
            )

        buttons = [c for c in iter_nodes(EachDtoBtnPage) if isinstance(c, Button)]
        assert read_anchor(buttons[0]) == 'EachDtoBtnPage.lst.$t[0]'


class TestItemSnapshot:
    def test_model_item_evaluate_round_trip(self) -> None:
        exprs: dict[str, Expr[Any]] = {}

        def render(m: Any) -> Text:
            exprs['label'] = m.text + '!'
            exprs['is_sys'] = ~m.mine
            return Text(m.text)

        each = Each(EachDtoState.messages, render=render)
        snapshot = item_snapshot(each, EachDtoMessage(id=7, text='收到', mine=False))
        assert exprs['label'].evaluate(snapshot) == '收到!'
        assert exprs['is_sys'].evaluate(snapshot) is True

    def test_scalar_item_snapshot(self) -> None:
        exprs: list[Expr[Any]] = []

        def render(tag: Any) -> Text:
            exprs.append(tag)
            return Text(tag)

        each = Each(EachDtoState.tags, render=render)
        assert exprs[0].evaluate(item_snapshot(each, 'beta')) == 'beta'

    def test_wrong_item_type_rejected(self) -> None:
        each = Each(EachDtoState.messages, render=lambda m: Text(m.text))
        with pytest.raises(TypeError, match='应为 EachDtoMessage'):
            item_snapshot(each, '不是模型')

    def test_item_ref_without_snapshot_raises(self) -> None:
        captured: list[Expr[Any]] = []

        def render(m: Any) -> Text:
            captured.append(m.text)
            return Text(m.text)

        Each(EachDtoState.messages, render=render)
        with pytest.raises(KeyError, match='item_snapshot'):
            captured[0].evaluate()
