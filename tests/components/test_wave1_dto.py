"""M2 Wave 1 组件 DTO:tag/敏感标记/受控声明/事件 kind/未知 prop 拒绝。"""

import pytest

from pyshade.components import (
    Alert,
    Badge,
    Checkbox,
    Progress,
    Separator,
    Skeleton,
    Textarea,
)
from pyshade.components.base import ControlledMixin, controlled_prop_of, is_sensitive

WAVE1 = (Badge, Alert, Separator, Skeleton, Progress, Textarea, Checkbox)


class TestWave1Dto:
    def test_shade_tags(self) -> None:
        tags = {cls._shade_tag for cls in WAVE1}  # pyright: ignore[reportPrivateUsage]
        assert tags == {'Badge', 'Alert', 'Separator', 'Skeleton', 'Progress', 'Textarea', 'Checkbox'}

    def test_none_sensitive(self) -> None:
        # §3.8 评估结论:Wave 1 无敏感组件
        for cls in WAVE1:
            assert is_sensitive(cls()) is False, cls.__name__

    def test_controlled_declarations(self) -> None:
        assert isinstance(Textarea(), ControlledMixin)
        assert controlled_prop_of(Textarea()) == 'value'
        assert isinstance(Checkbox(), ControlledMixin)
        assert controlled_prop_of(Checkbox()) == 'checked'
        assert not isinstance(Badge(), ControlledMixin)

    def test_unknown_prop_rejected(self) -> None:
        with pytest.raises(TypeError):
            Badge(nonexistent=1)  # pyright: ignore[reportCallIssue]

    def test_progress_accepts_numeric(self) -> None:
        int_value = Progress(50).value
        float_value = Progress(12.5).value
        assert isinstance(int_value, int) and int_value == 50
        assert isinstance(float_value, float) and float_value == 12.5

    def test_change_event_kinds(self) -> None:
        from pyshade.components.base import EventSpec

        for cls in (Textarea, Checkbox):
            field = cls.model_fields['on_change']
            specs = [m for m in field.metadata if isinstance(m, EventSpec)]
            assert specs and specs[0].kind == 'change', cls.__name__
