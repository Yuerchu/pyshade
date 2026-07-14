"""编译器中间表示:将 Page 子类的组件树转换为 IR 节点树(设计 §3.1 三分法)。

M1 起 PropInfo 携带 binding 分类(所有权公理,design.md §3.4):
plain=服务端所有(rt.ov 可 patch)/ expr=客户端所有(内联 JS)/
client_bind=受控 prop 绑定 ClientVal(共用 useState,唯一写者)/
server_ref=ServerState 字段(Phase 3)。
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pyshade.components.base import Component, ControlledMixin, EventSpec, controlled_prop_of, is_sensitive
from pyshade.expr import ClientVal, Expr
from pyshade.page import Page, anchor_of, iter_children

PropBinding = Literal['plain', 'expr', 'client_bind', 'server_ref']


@dataclass(frozen=True, slots=True)
class PropInfo:
    name: str
    default_value: Any
    is_enum: bool
    binding: PropBinding = 'plain'


@dataclass(frozen=True, slots=True)
class EventInfo:
    field_name: str
    kind: str
    handler_id: str


@dataclass(slots=True)
class NodeIR:
    anchor: str
    component: Component
    tag: str
    props: list[PropInfo] = field(default_factory=list[PropInfo])
    events: list[EventInfo] = field(default_factory=list[EventInfo])
    children: list['NodeIR'] = field(default_factory=list['NodeIR'])
    sensitive: bool = False


def _is_enum_field(value: object) -> bool:
    from enum import Enum

    return isinstance(value, Enum)


def _classify_binding(component: Component, name: str, value: object) -> PropBinding:
    if not isinstance(value, Expr):
        return 'plain'
    if (
        isinstance(value, ClientVal)
        and isinstance(component, ControlledMixin)
        and name == controlled_prop_of(component)
    ):
        return 'client_bind'
    return 'expr'


def build_node_ir(component: Component) -> NodeIR:
    """递归构建单个组件的 IR 节点。"""
    anchor = anchor_of(component)
    tag = type(component)._shade_tag  # pyright: ignore[reportPrivateUsage]
    props: list[PropInfo] = []
    events: list[EventInfo] = []

    for name, field_info in type(component).model_fields.items():
        specs = [m for m in field_info.metadata if isinstance(m, EventSpec)]
        if specs:
            handler = getattr(component, name)
            if handler is not None:
                events.append(EventInfo(field_name=name, kind=specs[0].kind, handler_id=f'{anchor}.{name}'))
            continue
        if name == 'children':
            continue
        value = getattr(component, name)
        props.append(
            PropInfo(
                name=name,
                default_value=value,
                is_enum=_is_enum_field(value),
                binding=_classify_binding(component, name, value),
            )
        )

    children_ir = [build_node_ir(child) for child in iter_children(component)]

    return NodeIR(
        anchor=anchor,
        component=component,
        tag=tag,
        props=props,
        events=events,
        children=children_ir,
        sensitive=is_sensitive(component),
    )


@dataclass(frozen=True, slots=True)
class PageIR:
    name: str
    page: type[Page]
    roots: list[NodeIR]
    client_vals: dict[str, ClientVal[Any]] = field(default_factory=dict[str, ClientVal[Any]])


def build_page_ir(page: type[Page]) -> PageIR:
    roots = [build_node_ir(root) for root in page.__shade_roots__]
    return PageIR(name=page.__name__, page=page, roots=roots, client_vals=dict(page.__shade_client_vals__))


def iter_node_irs(page_ir: PageIR) -> 'list[NodeIR]':
    """前序展开页面全部 IR 节点(checks 与 emit 共用)。"""
    out: list[NodeIR] = []

    def walk(node: NodeIR) -> None:
        out.append(node)
        for child in node.children:
            walk(child)

    for root in page_ir.roots:
        walk(root)
    return out
