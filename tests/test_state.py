"""ServerState:描述符双语义、单例、字段校验、contextvar sink 三态(design.md §3.3)。"""

from typing import Any, cast

import pytest
from pydantic import ValidationError

from pyshade.state import PatchSink, ServerRef, ServerState, ServerStateError, patch_sink


class ChatState(ServerState):
    status: str = '就绪'
    busy: bool = False
    count: int = 0


chat = ChatState()


class TestDescriptor:
    def test_class_access_yields_server_ref(self) -> None:
        ref = ChatState.__shade_fields__['status'].ref
        assert isinstance(ref, ServerRef)
        assert ref.target == '$s:ChatState'
        assert ref.field == 'status'
        assert ref.default == '就绪'

    def test_class_access_via_attribute(self) -> None:
        # 注解写裸 str(实例语义诚实),运行期类访问经描述符返回 ServerRef
        ref: object = ChatState.status
        assert isinstance(ref, ServerRef)

    def test_instance_access_yields_value(self) -> None:
        assert chat.status == '就绪'
        assert chat.busy is False

    def test_assignment_updates_value(self) -> None:
        chat.count = 42
        assert chat.count == 42
        chat.count = 0

    def test_assignment_validates_type(self) -> None:
        with pytest.raises(ValidationError):
            chat.status = object()  # pyright: ignore[reportAttributeAccessIssue]

    def test_singleton(self) -> None:
        with pytest.raises(RuntimeError, match='单例'):
            ChatState()

    def test_server_ref_bool_raises(self) -> None:
        ref = ChatState.__shade_fields__['busy'].ref
        with pytest.raises(TypeError, match='布尔上下文'):
            bool(ref)

    def test_server_ref_eq_raises(self) -> None:
        ref = ChatState.__shade_fields__['status'].ref
        with pytest.raises(TypeError, match='实例访问'):
            ref == 'x'  # pyright: ignore[reportUnusedExpression]  # noqa: B015

    def test_server_ref_str_raises(self) -> None:
        ref = ChatState.__shade_fields__['status'].ref
        with pytest.raises(TypeError, match='f-string'):
            str(ref)

    def test_server_ref_fstring_raises(self) -> None:
        ref = ChatState.__shade_fields__['status'].ref
        with pytest.raises(TypeError, match='f-string'):
            f'状态:{ref}'  # noqa: B018

    def test_server_ref_repr_still_available(self) -> None:
        ref = ChatState.__shade_fields__['status'].ref
        assert 'ServerRef' in repr(ref)


class TestClassLevelWrite:
    """类级赋值会替换 ServerField 描述符,静默断掉校验与 auto-diff——metaclass 拦截。"""

    def test_class_level_field_assignment_rejected(self) -> None:
        with pytest.raises(ServerStateError, match='类级赋值'):
            ChatState.status = 'done'

    def test_class_level_field_delete_rejected(self) -> None:
        with pytest.raises(ServerStateError, match='删除字段描述符'):
            del ChatState.status

    def test_non_field_class_attribute_allowed(self) -> None:
        probe = cast('Any', ChatState)  # 动态属性访问:metaclass 只冻结字段名
        probe.helper = 1
        assert probe.helper == 1
        del probe.helper


class TestInheritance:
    def test_field_bearing_subclass_inheritance_rejected(self) -> None:
        with pytest.raises(ServerStateError, match='组合'):

            class ChildOfChat(ChatState):
                extra: int = 0

    def test_fieldless_mixin_allowed(self) -> None:
        class LogMixinState(ServerState):
            def describe(self) -> str:
                return type(self).__name__

        class MixinUserState(LogMixinState):
            label: str = 'x'

        assert list(MixinUserState.__shade_fields__) == ['label']
        instance = MixinUserState()
        assert instance.label == 'x'
        assert instance.describe() == 'MixinUserState'


class TestStringAnnotations:
    def test_pep563_module_rejected(self) -> None:
        import sys
        import types

        source = (
            'from __future__ import annotations\n'
            'from pyshade.state import ServerState\n'
            'class Pep563ProbeState(ServerState):\n'
            '    x: int = 0\n'
        )
        module = types.ModuleType('pep563_probe')
        sys.modules['pep563_probe'] = module
        try:
            with pytest.raises(ServerStateError, match='__future__'):
                exec(compile(source, '<pep563_probe>', 'exec'), module.__dict__)
        finally:
            del sys.modules['pep563_probe']

    def test_manual_string_annotation_rejected(self) -> None:
        with pytest.raises(ServerStateError, match='字符串'):
            type('StrAnnoState', (ServerState,), {'__annotations__': {'x': 'int'}, 'x': 0})


class TestClassDefinition:
    def test_missing_default_rejected(self) -> None:
        with pytest.raises(ServerStateError, match='缺少默认值'):

            class NoDefaultState(ServerState):
                value: str

    def test_non_json_default_rejected(self) -> None:
        with pytest.raises(ServerStateError, match='JSON'):

            class BadDefaultState(ServerState):
                value: object = object()

    def test_default_validated_against_annotation(self) -> None:
        with pytest.raises(ValidationError):

            class WrongDefaultState(ServerState):
                value: int = 'not-an-int'  # pyright: ignore[reportAssignmentType]

    def test_private_and_classvar_skipped(self) -> None:
        from typing import ClassVar

        class SkipState(ServerState):
            visible_field: str = 'x'
            _private: str = 'ignored'
            constant: ClassVar[str] = 'ignored'

        assert list(SkipState.__shade_fields__) == ['visible_field']

    def test_class_name_collision_rejected(self) -> None:
        class UniqueNameState(ServerState):
            value: int = 0

        with pytest.raises(ServerStateError, match='类名冲突'):
            type('UniqueNameState', (ServerState,), {'__annotations__': {'value': int}, 'value': 0})


class TestPatchSinkThreeStates:
    def test_init_does_not_dispatch(self) -> None:
        with patch_sink() as sink:

            class InitOnlyState(ServerState):
                value: str = '初始'

            InitOnlyState()
            assert sink.to_patches() == []

    def test_assignment_inside_sink_recorded(self) -> None:
        with patch_sink() as sink:
            chat.status = '处理中'
            chat.busy = True
        assert sink.to_patches() == [{'target': '$s:ChatState', 'props': {'status': '处理中', 'busy': True}}]
        chat.status = '就绪'
        chat.busy = False

    def test_last_write_wins(self) -> None:
        with patch_sink() as sink:
            chat.count = 1
            chat.count = 2
        assert sink.to_patches() == [{'target': '$s:ChatState', 'props': {'count': 2}}]
        chat.count = 0

    def test_closed_sink_not_recorded(self) -> None:
        # 后台任务继承 contextvar 快照:请求定稿后写入不得混入已发响应
        with patch_sink() as sink:
            chat.status = '请求内'
        chat.status = '请求外'  # sink 已 closed
        assert sink.to_patches() == [{'target': '$s:ChatState', 'props': {'status': '请求内'}}]
        assert chat.status == '请求外'
        chat.status = '就绪'

    def test_no_sink_does_not_crash(self) -> None:
        chat.count = 7
        assert chat.count == 7
        chat.count = 0

    def test_sink_is_fresh_per_context(self) -> None:
        with patch_sink() as first:
            chat.busy = True
        with patch_sink() as second:
            pass
        assert first.to_patches() != []
        assert second.to_patches() == []
        chat.busy = False

    def test_sink_dataclass_defaults(self) -> None:
        sink = PatchSink()
        assert sink.closed is False
        assert sink.to_patches() == []
