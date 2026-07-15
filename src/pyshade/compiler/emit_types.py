"""types.gen.ts:枚举 → TS union;Each 项模型 → TS interface(设计 §3.5)。"""

from enum import Enum

from pydantic import BaseModel

from pyshade.compiler.ir import PageIR
from pyshade.compiler.writer import TsxWriter

_TS_SCALAR: dict[object, str] = {bool: 'boolean', int: 'number', float: 'number', str: 'string'}


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


def collect_item_models(pages: list[PageIR]) -> list[type[BaseModel]]:
    """收集全部 Each 项模型(去重,按类名排序);.map 回调的 item 参数类型来源。"""
    from pyshade.compiler.ir import iter_node_irs
    from pyshade.components.each import Each, item_model_of

    seen: dict[str, type[BaseModel]] = {}
    for page_ir in pages:
        for node in iter_node_irs(page_ir):
            if node.tag != 'Each':
                continue
            model = item_model_of(node.component) if isinstance(node.component, Each) else None
            if model is not None and model.__name__ not in seen:
                seen[model.__name__] = model
    return [seen[name] for name in sorted(seen)]


def emit_types(enums: list[type[Enum]], models: list[type[BaseModel]] | None = None) -> str:
    """生成 types.gen.ts:Enum → export type union;项模型 → export interface(字段按声明序)。"""
    w = TsxWriter()
    w.line('/* 由 pyshade 编译器生成 — 请勿手改。 */')
    w.line()
    for enum_cls in enums:
        members = [f'"{m.value}"' for m in enum_cls]
        w.line(f'export type {enum_cls.__name__} = {" | ".join(members)};')
        w.line()
    for model in models or []:
        w.line(f'export interface {model.__name__} {{')
        w.indent()
        for name, field in model.model_fields.items():
            w.line(f'{name}: {_TS_SCALAR[field.annotation]};')
        w.dedent()
        w.line('}')
        w.line()
    return w.to_string()
