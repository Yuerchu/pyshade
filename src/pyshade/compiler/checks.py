"""编译期校验(设计 §3.5):事件签名、敏感组件断言、命名冲突。

M1 新增表达式 G 规则(格式沿用"页面.字段 → 错误 → 修复建议"):
死引用/跨页引用/类型不匹配/敏感源/ClientVal 唯一写者/零绑定告警/变量名冲突。
"""

import warnings
from dataclasses import dataclass, field
from typing import Any, cast, get_args

from pyshade.compiler.errors import CompileError
from pyshade.compiler.ir import NodeIR, PageIR, PropInfo, iter_node_irs
from pyshade.components.base import Component, EventSpec, is_sensitive, read_anchor
from pyshade.events import validate_handler
from pyshade.expr import ClientVal, Expr, ExprType, PropRef, read_owner
from pyshade.state import ServerRef

_JS_RESERVED = frozenset(
    {
        'break',
        'case',
        'catch',
        'continue',
        'debugger',
        'default',
        'delete',
        'do',
        'else',
        'finally',
        'for',
        'function',
        'if',
        'in',
        'instanceof',
        'new',
        'return',
        'switch',
        'this',
        'throw',
        'try',
        'typeof',
        'var',
        'void',
        'while',
        'with',
        'class',
        'const',
        'enum',
        'export',
        'extends',
        'import',
        'super',
        'implements',
        'interface',
        'let',
        'package',
        'private',
        'protected',
        'public',
        'static',
        'yield',
    }
)


@dataclass
class _ExprState:
    """页面级 ClientVal 记账:唯一写者与零绑定告警的依据。"""

    bind_sites: dict[int, list[str]] = field(default_factory=dict[int, list[str]])
    ref_sites: dict[int, str] = field(default_factory=dict[int, str])
    vals_by_id: dict[int, str] = field(default_factory=dict[int, str])


def check_page_ir(page_ir: PageIR) -> None:
    """对整个页面 IR 做编译期校验;失败抛 CompileError。"""
    seen_anchors: set[str] = set()
    state = _ExprState(vals_by_id={id(val): name for name, val in page_ir.client_vals.items()})
    for root in page_ir.roots:
        _check_node(root, page_ir.name, seen_anchors, state)
    _check_client_val_writers(page_ir, state)
    _check_var_collisions(page_ir)


def _check_node(node: NodeIR, page_name: str, seen: set[str], state: _ExprState) -> None:
    if node.anchor in seen:
        raise CompileError(f"{node.anchor}: anchor 重复(内部错误)")
    seen.add(node.anchor)

    _check_naming(node, page_name)
    _check_sensitive(node)
    _check_event_handlers(node)
    _check_component_rules(node)
    for prop in node.props:
        if prop.binding == 'client_bind':
            _check_client_bind(node, prop, page_name, state)
        elif prop.binding == 'expr':
            _check_expr_prop(node, prop, page_name, state)
        elif prop.binding == 'server_ref':
            _check_server_ref(node, prop)

    for child in node.children:
        _check_node(child, page_name, seen, state)


def _check_naming(node: NodeIR, page_name: str) -> None:
    parts = node.anchor.split('.')
    local_name = parts[-1].split('[')[0] if '[' in parts[-1] else parts[-1]
    if local_name in _JS_RESERVED:
        raise CompileError(f"{node.anchor}: 字段名 '{local_name}' 是 JavaScript 保留字,请换个名字")


def _check_sensitive(node: NodeIR) -> None:
    if not node.sensitive:
        return
    for field_name, field_info in type(node.component).model_fields.items():
        if any(isinstance(m, EventSpec) for m in field_info.metadata):
            handler = getattr(node.component, field_name)
            if handler is not None:
                raise CompileError(f"{node.anchor}: 敏感组件({node.tag})不允许绑定事件 handler '{field_name}'")


def _check_event_handlers(node: NodeIR) -> None:
    for event in node.events:
        handler = getattr(node.component, event.field_name)
        try:
            validate_handler(handler, owner=event.handler_id)
        except Exception as exc:
            raise CompileError(str(exc)) from exc


_NUMERIC_TYPES = frozenset({ExprType.INT, ExprType.FLOAT})

_SCALAR_BY_PY_TYPE: dict[object, ExprType] = {
    bool: ExprType.BOOL,
    str: ExprType.STR,
    int: ExprType.INT,
    float: ExprType.FLOAT,
}


def _check_component_rules(node: NodeIR) -> None:
    """组件特有规则(按 tag 分发)。"""
    if node.tag == 'Progress':
        value = next((p for p in node.props if p.name == 'value'), None)
        if value is not None and value.binding == 'plain':
            v = value.default_value
            if isinstance(v, (int, float)) and not 0 <= v <= 100:
                raise CompileError(f"{_site(node, value)}: Progress 取值 {v} 越界 → 取值范围 0-100")
    elif node.tag in ('Select', 'RadioGroup'):
        _check_options(node)
    elif node.tag == 'Slider':
        _check_slider(node)


def _check_options(node: NodeIR) -> None:
    from pyshade.components.options import Option

    options_prop = next(p for p in node.props if p.name == 'options')
    options = cast('list[Option]', options_prop.default_value)
    if not options:
        raise CompileError(f"{_site(node, options_prop)}: 选项列表为空 → 请至少提供一个选项")
    seen: set[str] = set()
    for option in options:
        if not option.value:
            raise CompileError(f"{_site(node, options_prop)}: 选项 value 不能为空串(radix Item 限制)→ 请提供非空 value")
        if option.value in seen:
            raise CompileError(f"{_site(node, options_prop)}: 选项 value '{option.value}' 重复 → value 必须唯一")
        seen.add(option.value)

    value_prop = next(p for p in node.props if p.name == 'value')
    default: object = value_prop.default_value
    if isinstance(default, ClientVal):
        default = cast('ClientVal[Any]', default).default
    if isinstance(default, str) and default and default not in seen:
        raise CompileError(f"{_site(node, value_prop)}: 默认值 '{default}' 不在选项中 → 请使用某个选项的 value 或留空")


def _check_slider(node: NodeIR) -> None:
    def plain_number(name: str) -> float | None:
        prop = next((p for p in node.props if p.name == name), None)
        if prop is None or prop.binding != 'plain':
            return None
        value = prop.default_value
        return float(value) if isinstance(value, (int, float)) else None

    minimum, maximum, step = plain_number('min'), plain_number('max'), plain_number('step')
    if minimum is not None and maximum is not None and minimum >= maximum:
        raise CompileError(f"{node.anchor}.min: Slider 区间非法(min={minimum} >= max={maximum})→ 请保证 min < max")
    if step is not None and step <= 0:
        raise CompileError(f"{node.anchor}.step: Slider step 必须为正数(收到 {step})")

    value_prop = next(p for p in node.props if p.name == 'value')
    default: object = value_prop.default_value
    if isinstance(default, ClientVal):
        default = cast('ClientVal[Any]', default).default
    if (
        isinstance(default, (int, float))
        and minimum is not None
        and maximum is not None
        and not minimum <= float(default) <= maximum
    ):
        raise CompileError(
            f"{_site(node, value_prop)}: 默认值 {default} 不在区间 [{minimum}, {maximum}] 内 → 请调整默认值或区间"
        )


def _expected_expr_types(component: Component, prop: str) -> set[ExprType]:
    """从 prop 注解(`T | Expr[T]` union)提取全部裸标量成员。"""
    annotation: object = type(component).model_fields[prop].annotation
    out: set[ExprType] = set()
    for arg in get_args(annotation) or (annotation,):
        scalar = _SCALAR_BY_PY_TYPE.get(arg)
        if scalar is not None:
            out.add(scalar)
    return out


def _type_compatible(actual: ExprType, expected: set[ExprType]) -> bool:
    """INT/FLOAT 同类别互通,与 expr._same_category 语义对齐(数值组件正常绑定)。"""
    if actual in expected:
        return True
    return actual in _NUMERIC_TYPES and bool(expected & _NUMERIC_TYPES)


def _site(node: NodeIR, prop: PropInfo) -> str:
    return f'{node.anchor}.{prop.name}'


def _check_type_match(node: NodeIR, prop: PropInfo, expr: 'Expr[Any]') -> None:
    expected = _expected_expr_types(node.component, prop.name)
    if expected and not _type_compatible(expr.type, expected):
        expected_names = '/'.join(sorted(t.value for t in expected))
        raise CompileError(
            f"{_site(node, prop)}: 表达式类型 {expr.type.value} 与 prop 类型 {expected_names} 不匹配 → "
            f"请让表达式产出 {expected_names}(比较/逻辑组合产出 bool,`+` 拼接产出 str)"
        )


def _check_client_bind(node: NodeIR, prop: PropInfo, page_name: str, state: _ExprState) -> None:
    val = cast('ClientVal[Any]', prop.default_value)
    _check_owned_by_page(node, prop, val, page_name)
    _check_type_match(node, prop, val)
    state.bind_sites.setdefault(id(val), []).append(_site(node, prop))


def _check_expr_prop(node: NodeIR, prop: PropInfo, page_name: str, state: _ExprState) -> None:
    expr = cast('Expr[Any]', prop.default_value)
    _check_type_match(node, prop, expr)
    for leaf in expr.refs():
        if isinstance(leaf, ClientVal):
            _check_owned_by_page(node, prop, leaf, page_name)
            state.ref_sites.setdefault(id(leaf), _site(node, prop))
        else:
            _check_prop_ref(node, prop, leaf, page_name)


def _scalar_type_of(value: object) -> ExprType | None:
    if isinstance(value, bool):  # bool 先于 int(子类)
        return ExprType.BOOL
    if isinstance(value, int):
        return ExprType.INT
    if isinstance(value, float):
        return ExprType.FLOAT
    if isinstance(value, str):
        return ExprType.STR
    return None


def _check_server_ref(node: NodeIR, prop: PropInfo) -> None:
    ref = cast('ServerRef[Any]', prop.default_value)
    if ref.field not in ref.state_class.__shade_fields__:
        raise CompileError(
            f"{_site(node, prop)}: {ref.state_class.__name__} 没有字段 '{ref.field}' → "
            "ServerRef 请通过类访问获得(如 ChatState.status),不要手工构造"
        )
    expected = _expected_expr_types(node.component, prop.name)
    actual = _scalar_type_of(ref.default)
    if expected and (actual is None or not _type_compatible(actual, expected)):
        actual_name = actual.value if actual is not None else type(ref.default).__name__
        expected_names = '/'.join(sorted(t.value for t in expected))
        raise CompileError(
            f"{_site(node, prop)}: ServerState 字段 {ref.target}.{ref.field} 的类型 {actual_name} "
            f"与 prop 类型 {expected_names} 不匹配 → 请调整字段类型或换一个 prop"
        )


def _check_owned_by_page(node: NodeIR, prop: PropInfo, val: 'ClientVal[Any]', page_name: str) -> None:
    owner = read_owner(val)
    if owner is None:
        raise CompileError(
            f"{_site(node, prop)}: 引用的 ClientVal 未声明为页面字段 → "
            f"请在 {page_name} 类体中以字段形式声明(如 `thinking = ClientVal(True)`)后再引用"
        )
    if not owner.startswith(f'{page_name}.'):
        raise CompileError(
            f"{_site(node, prop)}: 引用了其他页面的 ClientVal({owner})→ "
            "客户端状态不跨页面,请在本页面声明独立的 ClientVal"
        )


def _check_prop_ref(node: NodeIR, prop: PropInfo, ref: 'PropRef[Any]', page_name: str) -> None:
    if is_sensitive(ref.component):
        raise CompileError(
            f"{_site(node, prop)}: 引用了敏感组件 {type(ref.component).__name__} 的值 → "
            "敏感值只随 submit=True 的事件跨界,不能作为表达式源(design.md §3.8)"
        )
    anchor = read_anchor(ref.component)
    if anchor is None:
        raise CompileError(
            f"{_site(node, prop)}: value_of() 引用的 {type(ref.component).__name__} 未挂载到任何 Page → "
            "请将该组件声明为页面字段或放入页面容器"
        )
    if not anchor.startswith(f'{page_name}.'):
        raise CompileError(f"{_site(node, prop)}: value_of() 跨页面引用了 {anchor} → 表达式只能引用本页面组件")


def _check_client_val_writers(page_ir: PageIR, state: _ExprState) -> None:
    for name, val in page_ir.client_vals.items():
        sites = state.bind_sites.get(id(val), [])
        if len(sites) > 1:
            raise CompileError(
                f"{page_ir.name}.{name}: ClientVal 有多个写者({', '.join(sites)})→ "
                "受控绑定即唯一写者,请拆成多个 ClientVal 或只保留一个绑定"
            )
        if not sites and id(val) in state.ref_sites:
            warnings.warn(
                f"{page_ir.name}.{name} 被 {state.ref_sites[id(val)]} 引用但没有任何受控组件绑定,"
                "值恒为默认值;若非有意的常量,请绑定到受控组件(checked=/value=)",
                UserWarning,
                stacklevel=2,
            )


def _check_var_collisions(page_ir: PageIR) -> None:
    """ClientVal 字段名与匿名组件路径变量名(如 card_0)冲突时,生成的 useState 变量会重名。"""
    taken: dict[str, str] = {}
    for node in iter_node_irs(page_ir):
        local = node.anchor.split('.')[-1].replace('[', '_').replace(']', '')
        taken[local] = node.anchor
    for name in page_ir.client_vals:
        if name in taken:
            raise CompileError(f"{page_ir.name}.{name}: ClientVal 与组件 {taken[name]} 生成的变量名冲突 → 请改名")
