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
from pyshade.expr import ClientVal, Expr, ExprType, ItemRef, PropRef, read_owner
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
        _check_node(root, page_ir.name, seen_anchors, state, parent_tag=None, loop_token=None)
    _check_client_val_writers(page_ir, state)
    _check_var_collisions(page_ir)


def check_app(page_irs: list[PageIR]) -> None:
    """App 级校验(M2 Phase 5):页面类名唯一(anchor/handlerId/路由的命名空间)、navigate 目标存在。"""
    names: set[str] = set()
    for page_ir in page_irs:
        if page_ir.name in names:
            raise CompileError(f"页面类名 '{page_ir.name}' 重复:anchor/handlerId/路由均以类名为命名空间 → 请重命名")
        names.add(page_ir.name)
    for page_ir in page_irs:
        for node in iter_node_irs(page_ir):
            for nav in node.navigations:
                if nav.target_page not in names:
                    raise CompileError(
                        f"{node.anchor}.{nav.field_name}: navigate 目标 '{nav.target_page}' "
                        "不在 ShadeApp.pages 中 → 请将该页面加入 pages 列表或修正页面名"
                    )


def _check_node(  # noqa: PLR0913  # 遍历状态天然多参(内部函数)
    node: NodeIR,
    page_name: str,
    seen: set[str],
    state: _ExprState,
    *,
    parent_tag: str | None,
    loop_token: object | None,
) -> None:
    if node.anchor in seen:
        raise CompileError(f"{node.anchor}: anchor 重复(内部错误)")
    seen.add(node.anchor)

    _check_naming(node, page_name)
    _check_sensitive(node)
    _check_event_handlers(node)
    _check_slot_nesting(node, parent_tag)
    if loop_token is not None:
        _check_template_node(node)
    _check_component_rules(node)
    for prop in node.props:
        if prop.binding == 'client_bind':
            _check_client_bind(node, prop, page_name, state)
        elif prop.binding == 'expr':
            _check_expr_prop(node, prop, page_name, state, loop_token=loop_token)
        elif prop.binding == 'server_ref':
            _check_server_ref(node, prop)

    child_token = loop_token
    if node.tag == 'Each':  # 嵌套 Each 已被 _check_template_node 拒绝,此处必在模板外
        from pyshade.components.each import Each, loop_token_of

        child_token = loop_token_of(cast('Each', node.component))
    for child in node.children:
        _check_node(child, page_name, seen, state, parent_tag=node.tag, loop_token=child_token)


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


# 多槽容器的声明式嵌套表(§3.5 "SelectItem 只能在 Select 内"的校验能力落地)
_SLOT_CHILD_OF: dict[str, str] = {'Tabs': 'TabItem', 'Accordion': 'AccordionItem'}
_ITEM_PARENT_OF: dict[str, str] = {'TabItem': 'Tabs', 'AccordionItem': 'Accordion'}


def _check_slot_nesting(node: NodeIR, parent_tag: str | None) -> None:
    required_parent = _ITEM_PARENT_OF.get(node.tag)
    if required_parent is not None and parent_tag != required_parent:
        location = f'{parent_tag} 内' if parent_tag else '根级'
        raise CompileError(f"{node.anchor}: {node.tag} 只能是 {required_parent} 的直接子组件(当前在 {location})")
    required_child = _SLOT_CHILD_OF.get(node.tag)
    if required_child is not None:
        values: set[str] = set()
        for child in node.children:
            if child.tag != required_child:
                raise CompileError(
                    f"{node.anchor}: {node.tag} 的子组件必须全为 {required_child}(收到 {child.tag})→ "
                    f"内容请放进 {required_child} 的 children"
                )
            item_value = str(getattr(child.component, 'value', ''))
            if item_value in values:
                raise CompileError(f"{child.anchor}: value '{item_value}' 重复 → 同一容器内 value 必须唯一")
            values.add(item_value)


def _check_component_rules(node: NodeIR) -> None:
    """组件特有规则(按 tag 分发)。"""
    if node.navigations:
        _check_navigation(node)
    if node.schemes:
        _check_scheme(node)
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
    elif node.tag == 'Tooltip':
        _check_tooltip(node)
    elif node.tag in ('Dialog', 'AlertDialog'):
        _check_dialog(node)


_TEMPLATE_WHITELIST = frozenset({'Text', 'Button', 'Card'})
"""Each 模板允许的组件(M2):受控/敏感/浮层组件的 per-item 状态归 M3。"""


def _check_template_node(node: NodeIR) -> None:
    """G-E 规则:模板内组件白名单、嵌套 Each、submit 禁用、plain visible 必须为 True。"""
    if node.tag == 'Each':
        raise CompileError(f"{node.anchor}: Each 不支持嵌套(M3)→ 请把内层列表拍平或拆成独立区域")
    if node.tag not in _TEMPLATE_WHITELIST:
        allowed = '/'.join(sorted(_TEMPLATE_WHITELIST))
        raise CompileError(
            f"{node.anchor}: {node.tag} 不能出现在 Each 模板内(M2 白名单:{allowed})→ "
            "per-item 受控状态与浮层归 M3,请简化模板或把交互移到列表外"
        )
    submit = next((p for p in node.props if p.name == 'submit'), None)
    if submit is not None and submit.default_value is True:
        raise CompileError(
            f"{node.anchor}: Each 模板内不支持 submit=True(collectValues 是页面级快照,无 per-item 语义)→ "
            "请改用普通事件 + ctx.item_index 定位数据"
        )
    visible = next((p for p in node.props if p.name == 'visible'), None)
    if visible is not None and visible.binding == 'plain' and visible.default_value is not True:
        raise CompileError(
            f"{node.anchor}: 模板内 plain visible 是构建期常量,恒 False 无意义 → "
            "显隐请绑定项字段表达式(如 visible=item.mine)或 ServerRef"
        )


def _check_navigation(node: NodeIR) -> None:
    """navigate 是纯客户端跳转,不产生 IPC:submit=True(需要 handler 收 values)与之互斥。"""
    submit = next((p for p in node.props if p.name == 'submit'), None)
    if submit is not None and submit.default_value is True:
        nav = node.navigations[0]
        raise CompileError(
            f"{node.anchor}.{nav.field_name}: submit=True 的按钮需要 handler 接收 values,"
            "navigate 不携带数据 → 请改用模块级 handler 并在服务端返回 Navigate(Page)"
        )


def _check_scheme(node: NodeIR) -> None:
    """set_color_scheme 是纯客户端配色切换,不产生 IPC:submit=True 与之互斥(同 navigate)。"""
    submit = next((p for p in node.props if p.name == 'submit'), None)
    if submit is not None and submit.default_value is True:
        scheme = node.schemes[0]
        raise CompileError(
            f"{node.anchor}.{scheme.field_name}: submit=True 的按钮需要 handler 接收 values,"
            "set_color_scheme 不携带数据 → 配色切换请放到非 submit 按钮上"
        )


def _check_tooltip(node: NodeIR) -> None:
    if len(node.children) != 1:
        raise CompileError(f"{node.anchor}: Tooltip 需要恰好一个宿主组件(收到 {len(node.children)} 个)")
    child = node.children[0]
    child_visible = next((p for p in child.props if p.name == 'visible'), None)
    if child_visible is not None and (child_visible.binding != 'plain' or child_visible.default_value is not True):
        raise CompileError(
            f"{child.anchor}: Tooltip 宿主的 visible 必须保持默认 True(asChild 单元素约束)→ "
            "显隐控制请放到 Tooltip 本身的 visible 上"
        )


def _check_dialog(node: NodeIR) -> None:
    trigger: object = getattr(node.component, 'trigger', None)
    if trigger is not None and getattr(trigger, 'on_click', None) is not None:
        raise CompileError(
            f"{node.anchor}.trigger: trigger 组件不得绑定 on_click(radix Trigger 接管点击,"
            "asChild 合并会双触发)→ 打开弹窗无需 handler,业务点击请放弹窗内的按钮"
        )
    open_prop = next(p for p in node.props if p.name == 'open')
    if trigger is None and open_prop.binding == 'plain' and open_prop.default_value is False:
        warnings.warn(
            f"{node.anchor}: 没有 trigger 且 open 恒为 False,弹窗永远无法打开;"
            "请提供 trigger= 或绑定 ClientVal 控制 open",
            UserWarning,
            stacklevel=2,
        )


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


def _check_expr_prop(
    node: NodeIR, prop: PropInfo, page_name: str, state: _ExprState, *, loop_token: object | None
) -> None:
    expr = cast('Expr[Any]', prop.default_value)
    _check_type_match(node, prop, expr)
    for leaf in expr.refs():
        if isinstance(leaf, ItemRef):
            if leaf.loop_token is not loop_token:
                raise CompileError(
                    f"{_site(node, prop)}: 项字段引用逃逸出其 Each 模板 → "
                    "ItemRef 只在所属 Each 的 render 模板内有意义,请勿存储代理属性供模板外使用"
                )
        elif isinstance(leaf, ClientVal):
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
