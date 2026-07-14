import pytest
from pydantic import ValidationError

from pyshade.components import (
    Button,
    ButtonVariant,
    Card,
    Component,
    EventSpec,
    Input,
    PasswordInput,
    Switch,
    Text,
)


class TestPropsValidation:
    def test_unknown_prop_rejected_at_construction(self) -> None:
        # 显式 __init__ 签名让未知 prop 在 Python 层即 TypeError(早于 Pydantic)
        with pytest.raises(TypeError):
            Button('ok', wrong_prop=True)  # type: ignore[call-arg]

    def test_unknown_prop_rejected_by_model_validate(self) -> None:
        # Pydantic v2 对自定义 __init__ 的模型,model_validate 也走 __init__(custom_init),
        # extra='forbid' 是防未来行为变化的双保险;此处只锁定"构造期必报错"
        with pytest.raises((ValidationError, TypeError)):
            Button.model_validate({'text': 'ok', 'wrong_prop': True})

    def test_wrong_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Text(text=123)  # type: ignore[arg-type]

    def test_enum_by_value(self) -> None:
        button = Button('x', variant=ButtonVariant.DESTRUCTIVE)
        assert button.variant.value == 'destructive'

    def test_visible_defaults_true(self) -> None:
        assert Text('x').visible is True


class TestInstanceIdentity:
    """布局单父检测与 anchor 刻写的前提:children 校验不拷贝实例(revalidate='never')。"""

    def test_children_keep_identity(self) -> None:
        inner = Text('inner')
        card = Card(inner, title='t')
        assert card.children[0] is inner

    def test_nested_children_keep_identity(self) -> None:
        leaf = Button('leaf')
        inner_card = Card(leaf)
        outer_card = Card(inner_card)
        first_child = outer_card.children[0]
        assert isinstance(first_child, Card)
        assert first_child.children[0] is leaf

    def test_revalidate_config_not_overridden(self) -> None:
        assert Component.model_config.get('revalidate_instances', 'never') == 'never'


class TestEventFields:
    def test_event_field_metadata(self) -> None:
        metadata = Button.model_fields['on_click'].metadata
        specs = [m for m in metadata if isinstance(m, EventSpec)]
        assert len(specs) == 1
        assert specs[0].kind == 'click'

    def test_change_event_metadata(self) -> None:
        for cls in (Input, Switch):
            specs = [m for m in cls.model_fields['on_change'].metadata if isinstance(m, EventSpec)]
            assert specs[0].kind == 'change'

    def test_handler_reference_stored(self) -> None:
        def on_click(ctx: object) -> None: ...

        assert Button('x', on_click=on_click).on_click is on_click


class TestSensitiveComponent:
    def test_password_input_is_sensitive(self) -> None:
        assert PasswordInput._sensitive is True  # pyright: ignore[reportPrivateUsage]
        assert Input._sensitive is False  # pyright: ignore[reportPrivateUsage]

    def test_password_input_has_no_event_fields(self) -> None:
        for field in PasswordInput.model_fields.values():
            assert not any(isinstance(m, EventSpec) for m in field.metadata)

    def test_password_input_rejects_change_handler(self) -> None:
        with pytest.raises(TypeError):
            PasswordInput(on_change=lambda ctx: None)  # type: ignore[call-arg]
        with pytest.raises((ValidationError, TypeError)):
            PasswordInput.model_validate({'on_change': 'x'})

    def test_password_input_has_no_value_prop(self) -> None:
        assert 'value' not in PasswordInput.model_fields


class TestShadeTags:
    def test_all_components_have_tags(self) -> None:
        for cls, tag in [
            (Text, 'Text'),
            (Button, 'Button'),
            (Input, 'Input'),
            (PasswordInput, 'PasswordInput'),
            (Switch, 'Switch'),
            (Card, 'Card'),
        ]:
            assert cls._shade_tag == tag  # pyright: ignore[reportPrivateUsage]
