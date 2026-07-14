"""枚举 → types.gen.ts:收集所有用到的 (str, Enum) 生成 TS union(设计 §3.5)。"""

from enum import Enum

from pyshade.compiler.ir import PageIR
from pyshade.compiler.writer import TsxWriter


def collect_enums(pages: list[PageIR]) -> list[type[Enum]]:
    """收集页面 IR 中所有引用的 Enum 类型(去重,按类名排序)。"""
    seen: dict[str, type[Enum]] = {}

    def _visit_props(page_ir: PageIR) -> None:
        for root in page_ir.roots:
            _visit_node_enums(root, seen)

    for page in pages:
        _visit_props(page)

    return [seen[name] for name in sorted(seen)]


def _visit_node_enums(node: object, seen: dict[str, type[Enum]]) -> None:
    from pyshade.compiler.ir import NodeIR

    if not isinstance(node, NodeIR):
        return
    for prop in node.props:
        if prop.is_enum and isinstance(prop.default_value, Enum):
            enum_cls = type(prop.default_value)
            if enum_cls.__name__ not in seen:
                seen[enum_cls.__name__] = enum_cls
    for child in node.children:
        _visit_node_enums(child, seen)


def emit_types(enums: list[type[Enum]]) -> str:
    """生成 types.gen.ts:每个 Enum → export type ... = "a" | "b" | ...。"""
    w = TsxWriter()
    w.line('/* 由 pyshade 编译器生成 — 请勿手改。 */')
    w.line()
    for enum_cls in enums:
        members = [f'"{m.value}"' for m in enum_cls]
        w.line(f'export type {enum_cls.__name__} = {" | ".join(members)};')
        w.line()
    return w.to_string()
