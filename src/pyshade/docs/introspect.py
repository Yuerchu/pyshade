"""组件 props 内省(M4,design.md §3.10):文档站 / llms.txt / 将来类型存根的共同数据源。

不走 `model_json_schema()`——JSON schema 表达不了绑定所有权(§3.3 五分类)与 EventSpec
事件语义;直接内省 `model_fields`:注解拆 union → 绑定形态,EventSpec metadata → 事件行,
`Field.description` → 描述列(英文 canonical,中文翻译表在文档站侧对账)。
"""

import types
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Literal, Union, cast, get_args, get_origin

from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from pyshade.actions import ClientAction
from pyshade.components.base import Component, EventSpec
from pyshade.expr import ClientVal, Expr
from pyshade.state import ServerRef

Binding = Literal['plain', 'expr', 'client_bind', 'server_ref', 'const']

_SCALAR_DISPLAY: dict[object, str] = {bool: 'bool', int: 'int', float: 'float', str: 'str'}


@dataclass(frozen=True, slots=True)
class FieldDoc:
    """一个 prop 的文档条目;事件字段以 event_kind 标记(bindings 为空)。"""

    name: str
    type_display: str
    bindings: tuple[Binding, ...]
    default_display: str | None
    """None = 必填(无默认值)。"""
    enum_values: tuple[str, ...] | None
    event_kind: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class ComponentDoc:
    tag: str
    class_name: str
    docstring: str
    fields: tuple[FieldDoc, ...]


def _strip_annotated(annotation: object) -> object:
    """剥掉 Annotated 外壳(可嵌套):`Annotated[int, Field(gt=0)]` 的本体是 int。
    此前静默退化为显示 'Annotated' 且标记检测失效。"""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _display_of(annotation: object) -> str:
    """单个非标记注解成员的展示串(标量/Literal/Enum/泛型递归展开/兜底 __name__)。"""
    annotation = _strip_annotated(annotation)
    scalar = _SCALAR_DISPLAY.get(annotation)
    if scalar is not None:
        return scalar
    if annotation is type(None):
        return 'None'
    if annotation is Ellipsis:
        return '...'  # tuple[int, ...] 的第二参
    origin = get_origin(annotation)
    if origin is Literal:
        return f'Literal[{", ".join(repr(arg) for arg in get_args(annotation))}]'
    if origin is Union or origin is types.UnionType:
        return ' | '.join(_display_of(member) for member in get_args(annotation))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation.__name__
    if annotation is Any:
        return 'Any'
    if origin is not None:
        args = get_args(annotation)
        if args:  # 参数化泛型递归展开:dict[str, int]/tuple[int, ...] 此前只显示裸 origin 名
            origin_name = getattr(origin, '__name__', None)
            display = origin_name if isinstance(origin_name, str) else str(origin)
            return f'{display}[{", ".join(_display_of(arg) for arg in args)}]'
    plain = cast('object', annotation)  # issubclass 窄化残留 type[Unknown],收敛回 object
    fallback = getattr(plain, '__name__', None)
    return fallback if isinstance(fallback, str) else str(plain)


def _union_members(annotation: object) -> tuple[object, ...]:
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return get_args(annotation)
    return (annotation,)


def _is_marker(member: object, marker: type) -> bool:
    origin = get_origin(member) or member
    return isinstance(origin, type) and issubclass(origin, marker)


def _default_display(info: FieldInfo) -> str | None:
    if info.default_factory is not None:
        factory = info.default_factory
        produced: object = factory()  # pyright: ignore[reportCallIssue]  # 组件字段的 factory 均无参
        return repr(produced)
    if info.default is PydanticUndefined:
        return None
    default: object = info.default
    if isinstance(default, Enum):
        return repr(default.value)
    return repr(default)


def _render_field(component: type[Component], name: str, info: FieldInfo) -> FieldDoc:
    specs = [m for m in info.metadata if isinstance(m, EventSpec)]
    members = _union_members(info.annotation)

    if specs:
        # 事件字段:Handler | ClientAction | None;绑定形态不适用
        accepts_action = any(_is_marker(m, ClientAction) for m in members)
        type_display = 'Handler | ClientAction' if accepts_action else 'Handler'
        return FieldDoc(
            name=name,
            type_display=type_display,
            bindings=(),
            default_display=_default_display(info),
            enum_values=None,
            event_kind=specs[0].kind,
            description=info.description,
        )

    bindings: list[Binding] = []
    plain_members: list[object] = []
    for member in members:
        member = _strip_annotated(member)  # Annotated[ServerRef[int], ...] 类形态的标记检测须先剥壳
        if member is type(None):
            continue
        if _is_marker(member, ClientVal):
            bindings.append('client_bind')
        elif _is_marker(member, Expr):
            bindings.append('expr')
        elif _is_marker(member, ServerRef):
            bindings.append('server_ref')
        elif get_origin(member) is Callable:
            continue  # 防御:非事件字段不应有 callable 成员
        else:
            plain_members.append(member)
    if plain_members:
        bindings.insert(0, 'plain')
    bindings = list(dict.fromkeys(bindings))  # Slider 类:ClientVal[int]|ClientVal[float] 去重
    if name in component._const_props:  # pyright: ignore[reportPrivateUsage]
        bindings = ['const']

    enum_values: tuple[str, ...] | None = None
    for member in plain_members:
        if isinstance(member, type) and issubclass(member, Enum):
            enum_values = tuple(str(item.value) for item in member)
        elif get_origin(member) is list:
            (item,) = get_args(member) or (object,)
            if isinstance(item, type) and issubclass(item, Enum):
                enum_values = tuple(str(entry.value) for entry in item)

    type_display = ' | '.join(dict.fromkeys(_display_of(m) for m in plain_members)) or 'Any'
    return FieldDoc(
        name=name,
        type_display=type_display,
        bindings=tuple(bindings),
        default_display=_default_display(info),
        enum_values=enum_values,
        event_kind=None,
        description=info.description,
    )


def component_doc(component: type[Component]) -> ComponentDoc:
    tag: str = component._shade_tag  # pyright: ignore[reportPrivateUsage]
    fields = tuple(_render_field(component, name, info) for name, info in component.model_fields.items())
    return ComponentDoc(
        tag=tag,
        class_name=component.__name__,
        docstring=(component.__doc__ or '').strip(),
        fields=fields,
    )


def collect_components() -> list[ComponentDoc]:
    """全组件文档条目(按 tag 排序);与编译器 EMITTERS 双向对账,缺一边即抛。"""
    # 触发全部 DTO 模块导入(__subclasses__ 才完整)
    import pyshade.components  # noqa: F401  # pyright: ignore[reportUnusedImport]
    from pyshade.compiler.emit_page import EMITTERS

    by_tag: dict[str, type[Component]] = {}
    for cls in Component.__subclasses__():
        tag: str = cls._shade_tag  # pyright: ignore[reportPrivateUsage]
        if not tag:
            continue
        if tag in by_tag:
            raise RuntimeError(f"组件 tag '{tag}' 重复:{by_tag[tag].__name__} 与 {cls.__name__}")
        by_tag[tag] = cls

    missing_emitter = sorted(set(by_tag) - set(EMITTERS))
    missing_dto = sorted(set(EMITTERS) - set(by_tag))
    if missing_emitter:
        raise RuntimeError(f"组件缺 emitter(compiler/emit_page.py @register):{', '.join(missing_emitter)}")
    if missing_dto:
        raise RuntimeError(f"emitter 缺组件 DTO(components/):{', '.join(missing_dto)}")

    return [component_doc(by_tag[tag]) for tag in sorted(by_tag)]
