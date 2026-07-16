"""props 内省(M4 §3.10):对账防漂移、绑定形态、事件行、描述全量、schema 冒烟。"""

import pytest

from pyshade.components import Component
from pyshade.docs import ComponentDoc, FieldDoc, collect_components

DOCS = {doc.tag: doc for doc in collect_components()}


def _field(doc: ComponentDoc, name: str) -> FieldDoc:
    entry = next((f for f in doc.fields if f.name == name), None)
    assert entry is not None, f'{doc.tag} 缺字段 {name}'
    return entry


class TestRegistry:
    def test_matches_emitters(self) -> None:
        from pyshade.compiler.emit_page import EMITTERS

        assert set(DOCS) == set(EMITTERS)

    def test_component_count(self) -> None:
        # 29 个 DTO 类(营销口径 26 = 不含 TabItem/AccordionItem 子槽件与 PasswordInput 变体)
        assert len(DOCS) == 29

    def test_docstrings_present(self) -> None:
        for doc in DOCS.values():
            assert doc.docstring, f'{doc.class_name} 缺类 docstring'


class TestDescriptionsComplete:
    """防漂移:加组件/加字段不写 description 即红(文档站描述列的供给保障)。"""

    def test_every_field_has_description(self) -> None:
        missing = [
            f'{doc.class_name}.{entry.name}' for doc in DOCS.values() for entry in doc.fields if not entry.description
        ]
        assert not missing, f"缺 Field(description=...):{', '.join(missing)}"


class TestFieldDocAnchors:
    def test_text_three_state(self) -> None:
        entry = _field(DOCS['Text'], 'text')
        assert entry.type_display == 'str'
        assert entry.bindings == ('plain', 'expr', 'server_ref')
        assert entry.default_display == "''"

    def test_visible_inherited_everywhere(self) -> None:
        for doc in DOCS.values():
            entry = _field(doc, 'visible')
            assert entry.bindings == ('plain', 'expr', 'server_ref'), doc.tag

    def test_button_event_row(self) -> None:
        entry = _field(DOCS['Button'], 'on_click')
        assert entry.event_kind == 'click'
        assert entry.type_display == 'Handler | ClientAction'
        assert entry.bindings == ()

    def test_change_event_plain_handler(self) -> None:
        entry = _field(DOCS['Input'], 'on_change')
        assert entry.event_kind == 'change'
        assert entry.type_display == 'Handler'

    def test_link_const(self) -> None:
        doc = DOCS['Link']
        assert _field(doc, 'href').bindings == ('const',)
        assert _field(doc, 'text').bindings == ('const',)
        assert _field(doc, 'href').default_display is None  # 必填

    def test_heading_level_literal(self) -> None:
        entry = _field(DOCS['Heading'], 'level')
        assert entry.bindings == ('const',)
        assert entry.type_display == 'Literal[1, 2, 3, 4]'
        assert entry.default_display == '2'

    def test_controlled_client_bind(self) -> None:
        entry = _field(DOCS['Switch'], 'checked')
        assert entry.bindings == ('plain', 'client_bind')
        assert entry.type_display == 'bool'

    def test_slider_numeric_dedup(self) -> None:
        entry = _field(DOCS['Slider'], 'value')
        assert entry.bindings == ('plain', 'client_bind')
        assert entry.type_display == 'int | float'

    def test_badge_enum_values(self) -> None:
        entry = _field(DOCS['Badge'], 'variant')
        assert entry.type_display == 'BadgeVariant'
        assert entry.enum_values == ('default', 'secondary', 'destructive', 'outline')

    def test_select_options_model_list(self) -> None:
        entry = _field(DOCS['Select'], 'options')
        assert entry.type_display == 'list[Option]'
        assert entry.default_display == '[]'

    def test_each_items(self) -> None:
        entry = _field(DOCS['Each'], 'items')
        assert 'server_ref' in entry.bindings


class TestJsonSchemaSmoke:
    """M4 前置修复:含 Expr/ServerRef/ClientAction union 的模型 model_json_schema() 不再炸。"""

    def test_all_components_json_schema(self) -> None:
        import pyshade.components  # noqa: F401  # pyright: ignore[reportUnusedImport]

        for cls in Component.__subclasses__():
            if not cls._shade_tag:  # pyright: ignore[reportPrivateUsage]
                continue
            schema = cls.model_json_schema()
            assert 'properties' in schema, cls.__name__


class TestRegistryGuards:
    def test_missing_emitter_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        # 包属性 emit_page 被同名函数遮蔽(compiler/__init__ 的 from-import),必须走 importlib
        emit_page_module = importlib.import_module('pyshade.compiler.emit_page')

        trimmed = dict(emit_page_module.EMITTERS)
        trimmed.pop('Text')
        monkeypatch.setattr(emit_page_module, 'EMITTERS', trimmed)
        with pytest.raises(RuntimeError, match='缺 emitter'):
            collect_components()
