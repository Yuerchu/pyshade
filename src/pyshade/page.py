"""Page 基类:类体中的 Component 实例字段即页面结构(计划 Part B 布局规则)。

收集机制用 `__init_subclass__`(不用 metaclass):页面类不是 Pydantic model,
与 ModelMetaclass 零冲突。规则:字段顺序=文档顺序(类体插入序);被容器引用的
字段自动移出根级;单父规则(`id()` 检测);匿名内联子组件 anchor 为路径形式,
"匿名+绑定事件"发 UserWarning(路径 id 会随兄弟插入漂移)。

`anchor_of` 与 `iter_nodes` 是编译器与 EventRegistry 共用的单一实现。
"""

import warnings
from collections.abc import Iterator
from typing import Any, ClassVar, cast

from pyshade.components.base import (
    Component,
    EventSpec,
    TemplateContainer,
    read_anchor,
    template_roots_of,
    write_anchor,
)
from pyshade.expr import ClientVal, read_owner, write_owner
from pyshade.nav import NavigateAction


class LayoutError(Exception):
    """页面布局非法:实例别名、单父冲突、跨页复用等。"""


def iter_children(component: Component) -> list[Component]:
    """收集组件的直接子组件:标量 Component 槽(如 Dialog.trigger)+ list[Component] 字段。

    顺序 = model_fields 声明序;标量槽由此获得稳定的匿名路径 anchor。
    """
    result: list[Component] = []
    for field_name in type(component).model_fields:
        value: object = getattr(component, field_name)
        if isinstance(value, Component):
            result.append(value)
        elif isinstance(value, list):
            items = cast('list[object]', value)
            result.extend(item for item in items if isinstance(item, Component))
    return result


def anchor_of(component: Component) -> str:
    """组件的稳定标识:handlerId 与 Update target 的共同来源。"""
    anchor = read_anchor(component)
    if anchor is None:
        raise LayoutError("组件尚未挂到任何 Page,无法取得 anchor")
    return anchor


def has_bound_events(component: Component) -> bool:
    """组件是否绑定了至少一个事件 handler(NavigateAction 无 handlerId,不算)。"""
    for name, field in type(component).model_fields.items():
        if not any(isinstance(m, EventSpec) for m in field.metadata):
            continue
        value: object = getattr(component, name)
        if value is not None and not isinstance(value, NavigateAction):
            return True
    return False


def _resolve_layout(page_name: str, named: list[tuple[str, Component]]) -> tuple[list[Component], dict[str, Component]]:
    named_by_id: dict[int, str] = {}
    for name, comp in named:
        if id(comp) in named_by_id:
            raise LayoutError(
                f"{page_name}.{name} 与 {page_name}.{named_by_id[id(comp)]} 是同一实例;组件实例不可复用,请分别创建"
            )
        named_by_id[id(comp)] = name

    for name, comp in named:
        existing = read_anchor(comp)
        if existing is not None:
            raise LayoutError(f"{page_name}.{name} 已属于 {existing};组件实例不可跨页面复用")

    anchors: dict[str, Component] = {}
    for name, comp in named:
        anchor = f'{page_name}.{name}'
        write_anchor(comp, anchor)
        anchors[anchor] = comp

    has_parent: set[int] = set()
    parent_anchor_of: dict[int, str] = {}

    def visit(parent: Component, *, in_template: bool = False) -> None:
        parent_anchor = read_anchor(parent)
        if parent_anchor is None:  # 防御:visit 只对已刻 anchor 的组件调用
            raise LayoutError("内部错误:父组件缺少 anchor")
        for index, child in enumerate(iter_children(parent)):
            child_id = id(child)
            if child_id in named_by_id:
                if in_template:
                    raise LayoutError(
                        f"{parent_anchor} 的模板引用了页面命名字段 {page_name}.{named_by_id[child_id]};"
                        "模板组件必须在 render 内新建"
                    )
                if child_id in has_parent:
                    raise LayoutError(
                        f"{page_name}.{named_by_id[child_id]} 同时出现在 "
                        f"{parent_anchor_of[child_id]} 和 {parent_anchor} 中;"
                        "每个组件实例只能有一个父容器"
                    )
                has_parent.add(child_id)
                parent_anchor_of[child_id] = parent_anchor
                # 命名子组件的 children 由顶层循环处理,此处不递归
            else:
                duplicate = read_anchor(child)
                if duplicate is not None:
                    raise LayoutError(f"{parent_anchor} 的匿名子组件已属于 {duplicate};组件实例不可复用,请分别创建")
                child_anchor = f'{parent_anchor}[{index}]'
                write_anchor(child, child_anchor)
                anchors[child_anchor] = child
                if has_bound_events(child) and not in_template:
                    # 模板节点天然匿名,handlerId 随模板重排漂移是编译期一体再生的,不告警
                    warnings.warn(
                        f"{child_anchor} 是匿名组件且绑定了事件,插入兄弟组件会导致 handlerId 漂移;"
                        "建议将其命名为页面字段",
                        UserWarning,
                        stacklevel=2,
                    )
                visit(child, in_template=in_template)
        if isinstance(parent, TemplateContainer):
            for index, template_root in enumerate(template_roots_of(parent)):
                root_id = id(template_root)
                if root_id in named_by_id:
                    raise LayoutError(
                        f"{parent_anchor} 的模板引用了页面命名字段 {page_name}.{named_by_id[root_id]};"
                        "模板组件必须在 render 内新建"
                    )
                duplicate = read_anchor(template_root)
                if duplicate is not None:
                    raise LayoutError(f"{parent_anchor} 的模板组件已属于 {duplicate};组件实例不可复用,请分别创建")
                template_anchor = f'{parent_anchor}.$t[{index}]'
                write_anchor(template_root, template_anchor)
                anchors[template_anchor] = template_root
                visit(template_root, in_template=True)

    for _name, comp in named:
        visit(comp)

    roots = [comp for _name, comp in named if id(comp) not in has_parent]
    return roots, anchors


def _resolve_client_vals(page_name: str, named: list[tuple[str, ClientVal[Any]]]) -> dict[str, ClientVal[Any]]:
    by_id: dict[int, str] = {}
    for name, val in named:
        if id(val) in by_id:
            raise LayoutError(f"{page_name}.{name} 与 {page_name}.{by_id[id(val)]} 是同一 ClientVal 实例;请分别创建")
        by_id[id(val)] = name

    for name, val in named:
        existing = read_owner(val)
        if existing is not None:
            raise LayoutError(f"{page_name}.{name} 已属于 {existing};ClientVal 不可跨页面复用")

    out: dict[str, ClientVal[Any]] = {}
    for name, val in named:
        write_owner(val, f'{page_name}.{name}')
        out[name] = val
    return out


class Page:
    """声明式页面基类:子类类体中的 Component 实例字段即页面结构,ClientVal 字段即客户端状态。"""

    __shade_roots__: ClassVar[list[Component]] = []
    __shade_anchors__: ClassVar[dict[str, Component]] = {}
    __shade_client_vals__: ClassVar[dict[str, ClientVal[Any]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        named_vals = cast(
            'list[tuple[str, ClientVal[Any]]]',
            [(name, value) for name, value in vars(cls).items() if isinstance(value, ClientVal)],
        )
        cls.__shade_client_vals__ = _resolve_client_vals(cls.__name__, named_vals)
        named = [(name, value) for name, value in vars(cls).items() if isinstance(value, Component)]
        roots, anchors = _resolve_layout(cls.__name__, named)
        cls.__shade_roots__ = roots
        cls.__shade_anchors__ = anchors


def iter_nodes(page: type[Page]) -> Iterator[Component]:
    """前序遍历页面全部组件,含模板子树(编译器与 EventRegistry 共用)。"""

    def walk(component: Component) -> Iterator[Component]:
        yield component
        for child in iter_children(component):
            yield from walk(child)
        if isinstance(component, TemplateContainer):
            for template_root in template_roots_of(component):
                yield from walk(template_root)

    for root in page.__shade_roots__:
        yield from walk(root)
