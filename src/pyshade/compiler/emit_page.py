"""页面级 TSX 发射器:每页一文件(设计 §3.3 / §3.4)。

每组件一个 emitter 函数(注册表分发);受控 Input → useState + onBlur;
PasswordInput → uncontrolled useRef;plain prop 显式 rt.ov(anchor, prop, 默认值)。

M1 所有权公理落点:expr prop 内联 to_js 产物(不包 rt.ov,服务端 patch 不可达);
client_bind 受控 prop 与 ClientVal 共用 useState(别名);全部客户端所有的
"anchor.prop" 汇入 usePageRuntime({ boundProps }) 供前端过滤误发 patch。
"""

from collections.abc import Callable
from typing import Any, cast

from pyshade.compiler.errors import CompileError
from pyshade.compiler.ir import NodeIR, PageIR, PropInfo, iter_node_irs
from pyshade.compiler.writer import TsxWriter, js_bool, js_string, js_value
from pyshade.components.switch import Switch
from pyshade.expr import ClientVal, Expr, ExprType, PropRef
from pyshade.page import anchor_of
from pyshade.state import ServerRef

EmitFn = Callable[[NodeIR, TsxWriter, '_PageEmitContext'], None]

EMITTERS: dict[str, EmitFn] = {}

_TS_TYPE: dict[ExprType, str] = {
    ExprType.BOOL: 'boolean',
    ExprType.STR: 'string',
    ExprType.INT: 'number',
    ExprType.FLOAT: 'number',
}


def register(tag: str) -> Callable[[EmitFn], EmitFn]:
    def decorator(fn: EmitFn) -> EmitFn:
        EMITTERS[tag] = fn
        return fn

    return decorator


class _PageEmitContext:
    def __init__(self) -> None:
        self.state_hooks: list[str] = []
        self.refs: list[str] = []
        self.imports: set[str] = set()
        self.controlled_inputs: list[NodeIR] = []
        self.sensitive_inputs: list[NodeIR] = []
        self.client_vals: list[tuple[str, ClientVal[Any]]] = []
        self.scope: dict[Expr[Any], str] = {}
        self.alias: dict[str, str] = {}
        """受控组件 anchor → 绑定的 ClientVal 字段名(共用其 useState)。"""
        self.bound_props: list[str] = []
        """客户端所有的 'anchor.prop'(expr/client_bind),文档序。"""
        self.uses_push: bool = False
        """页面含 ServerRef 绑定 → usePageRuntime({ push: true }) 订阅 /_shade/push。"""

    def add_controlled(self, node: NodeIR) -> None:
        self.controlled_inputs.append(node)

    def add_sensitive(self, node: NodeIR) -> None:
        self.sensitive_inputs.append(node)

    def value_var(self, node: NodeIR) -> str:
        base = self.alias.get(node.anchor) or _var_name(node.anchor)
        return f'{base}Value'

    def setter(self, node: NodeIR) -> str:
        base = self.alias.get(node.anchor) or _var_name(node.anchor)
        return f'set{base.capitalize()}Value'

    def prop_js(self, node: NodeIR, prop: PropInfo) -> str:
        if prop.binding == 'expr':
            return cast('Expr[Any]', prop.default_value).to_js(self.scope)
        if prop.binding == 'server_ref':
            ref = cast('ServerRef[Any]', prop.default_value)
            return f'rt.ov({js_string(ref.target)}, {js_string(ref.field)}, {js_value(ref.default)})'
        return _ov(node.anchor, prop.name, prop.default_value)


def _var_name(anchor: str) -> str:
    return anchor.split('.')[-1].replace('[', '_').replace(']', '')


def _opt_prop(node: NodeIR, name: str) -> PropInfo | None:
    """可选 prop(label/placeholder/title/description):普通值为 None 时不发射属性。

    `rt.ov(..., null)` 会撞上 shadcn 的 `string | undefined` 注解(tsc 报错)。
    """
    prop = next((p for p in node.props if p.name == name), None)
    if prop is not None and prop.binding == 'plain' and prop.default_value is None:
        return None
    return prop


def _ov(anchor: str, prop: str, default: object) -> str:
    return f'rt.ov({js_string(anchor)}, {js_string(prop)}, {js_value(default)})'


def _prepare_bindings(page_ir: PageIR, ctx: _PageEmitContext) -> None:
    """预扫描:构建 ClientVal scope、受控别名、boundProps(checks 已保证合法性)。"""
    ctx.client_vals = list(page_ir.client_vals.items())
    val_names: dict[int, str] = {id(val): name for name, val in ctx.client_vals}
    for name, val in ctx.client_vals:
        ctx.scope[val] = f'{name}Value'

    nodes = iter_node_irs(page_ir)
    for node in nodes:
        for prop in node.props:
            if prop.binding == 'client_bind':
                val = cast('ClientVal[Any]', prop.default_value)
                name = val_names.get(id(val))
                if name is None:
                    raise CompileError(f"{node.anchor}.{prop.name}: 绑定的 ClientVal 未声明为本页面字段")
                ctx.alias[node.anchor] = name

    for node in nodes:
        for prop in node.props:
            if prop.binding == 'server_ref':
                ctx.uses_push = True
            if prop.binding not in ('expr', 'client_bind'):
                continue
            ctx.bound_props.append(f'{node.anchor}.{prop.name}')
            if prop.binding != 'expr':
                continue
            for leaf in cast('Expr[Any]', prop.default_value).refs():
                if leaf in ctx.scope:
                    continue
                if isinstance(leaf, PropRef):
                    anchor = anchor_of(leaf.component)
                    base = ctx.alias.get(anchor) or _var_name(anchor)
                    ctx.scope[leaf] = f'{base}Value'
                else:
                    raise CompileError(f"{node.anchor}.{prop.name}: 引用的 ClientVal 未声明为本页面字段")


def _emit_visible_guard(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> bool:
    visible_prop = next((p for p in node.props if p.name == 'visible'), None)
    if visible_prop is None:
        return False
    if visible_prop.binding == 'expr':
        js = cast('Expr[Any]', visible_prop.default_value).to_js(ctx.scope)
        w.line(f'{{({js}) && (')
        w.indent()
        return True
    if visible_prop.binding == 'server_ref' or visible_prop.default_value is True:
        w.line(f'{{{ctx.prop_js(node, visible_prop)} && (')
        w.indent()
        return True
    return False


def _close_visible_guard(guarded: bool, w: TsxWriter) -> None:
    if guarded:
        w.dedent()
        w.line(')}')


@register('Text')
def emit_text(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    guarded = _emit_visible_guard(node, w, ctx)
    muted = next((p for p in node.props if p.name == 'muted'), None)
    text = next((p for p in node.props if p.name == 'text'), None)
    class_name = ' className="text-muted-foreground"' if muted and muted.default_value else ''
    text_js = ctx.prop_js(node, text) if text else js_string('')
    w.line(f'<p{class_name}>{{{text_js}}}</p>')
    _close_visible_guard(guarded, w)


@register('Button')
def emit_button(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Button')
    guarded = _emit_visible_guard(node, w, ctx)
    variant = next((p for p in node.props if p.name == 'variant'), None)
    size = next((p for p in node.props if p.name == 'size'), None)
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    text = next((p for p in node.props if p.name == 'text'), None)
    submit = next((p for p in node.props if p.name == 'submit'), None)
    click_event = next((e for e in node.events if e.kind == 'click'), None)

    is_submit = submit is not None and submit.default_value is True
    attrs: list[str] = []
    if variant:
        attrs.append(f'variant={{{ctx.prop_js(node, variant)}}}')
    if size:
        attrs.append(f'size={{{ctx.prop_js(node, size)}}}')
    if disabled:
        attrs.append(f'disabled={{{ctx.prop_js(node, disabled)}}}')
    if click_event:
        hid = js_string(click_event.handler_id)
        if is_submit:
            attrs.append(f'onClick={{() => rt.fire({hid}, {{ values: collectValues(true) }})}}')
        else:
            attrs.append(f'onClick={{() => rt.fire({hid}, {{}})}}')

    text_val = ctx.prop_js(node, text) if text else js_string('')
    w.line(f'<Button {" ".join(attrs)}>')
    w.indent()
    w.line(f'{{{text_val}}}')
    w.dedent()
    w.line('</Button>')
    _close_visible_guard(guarded, w)


@register('Input')
def emit_input(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Input')
    ctx.imports.add('Label')
    ctx.add_controlled(node)
    var = ctx.value_var(node)
    setter = ctx.setter(node)
    guarded = _emit_visible_guard(node, w, ctx)

    label = _opt_prop(node, 'label')
    placeholder = _opt_prop(node, 'placeholder')
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    change_event = next((e for e in node.events if e.kind == 'change'), None)

    w.line('<div className="grid gap-2">')
    w.indent()
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{ctx.prop_js(node, label)}}}</Label>')
    attrs: list[str] = [f'id={js_string(node.anchor)}']
    if placeholder:
        attrs.append(f'placeholder={{{ctx.prop_js(node, placeholder)}}}')
    if disabled:
        attrs.append(f'disabled={{{ctx.prop_js(node, disabled)}}}')
    attrs.append(f'value={{{var}}}')
    attrs.append(f'onChange={{(e) => {setter}(e.target.value)}}')
    if change_event:
        attrs.append(f'onBlur={{() => rt.fire({js_string(change_event.handler_id)}, {{ value: {var} }})}}')
    w.line(f'<Input {" ".join(attrs)} />')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


@register('PasswordInput')
def emit_password_input(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Input')
    ctx.imports.add('Label')
    ctx.add_sensitive(node)
    var = _var_name(node.anchor)
    guarded = _emit_visible_guard(node, w, ctx)

    label = _opt_prop(node, 'label')
    placeholder = _opt_prop(node, 'placeholder')
    disabled = next((p for p in node.props if p.name == 'disabled'), None)

    w.line('<div className="grid gap-2">')
    w.indent()
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{ctx.prop_js(node, label)}}}</Label>')
    attrs: list[str] = [
        f'id={js_string(node.anchor)}',
        'type="password"',
        'autoComplete="current-password"',
        f'ref={{{var}Ref}}',
    ]
    if placeholder:
        attrs.append(f'placeholder={{{ctx.prop_js(node, placeholder)}}}')
    if disabled:
        attrs.append(f'disabled={{{ctx.prop_js(node, disabled)}}}')
    w.line(f'<Input {" ".join(attrs)} />')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


@register('Switch')
def emit_switch(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Switch')
    ctx.imports.add('Label')
    ctx.add_controlled(node)
    var = ctx.value_var(node)
    setter = ctx.setter(node)
    guarded = _emit_visible_guard(node, w, ctx)

    label = _opt_prop(node, 'label')
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    change_event = next((e for e in node.events if e.kind == 'change'), None)

    w.line('<div className="flex items-center gap-2">')
    w.indent()

    attrs: list[str] = [
        f'id={js_string(node.anchor)}',
        f'checked={{{var}}}',
    ]
    if disabled:
        attrs.append(f'disabled={{{ctx.prop_js(node, disabled)}}}')

    change_parts: list[str] = [f'{setter}(checked)']
    if change_event:
        change_parts.append(f'rt.fire({js_string(change_event.handler_id)}, {{ value: checked }})')
    change_body = '; '.join(change_parts)
    attrs.append(f'onCheckedChange={{(checked) => {{ {change_body} }}}}')

    w.line(f'<Switch {" ".join(attrs)} />')
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{ctx.prop_js(node, label)}}}</Label>')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


@register('Card')
def emit_card(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Card')
    ctx.imports.add('CardContent')
    guarded = _emit_visible_guard(node, w, ctx)

    title = _opt_prop(node, 'title')
    description = _opt_prop(node, 'description')

    w.line('<Card className="w-full max-w-sm">')
    w.indent()
    if title or description:
        ctx.imports.add('CardHeader')
        w.line('<CardHeader>')
        w.indent()
        if title:
            ctx.imports.add('CardTitle')
            w.line(f'<CardTitle>{{{ctx.prop_js(node, title)}}}</CardTitle>')
        if description:
            ctx.imports.add('CardDescription')
            w.line(f'<CardDescription>{{{ctx.prop_js(node, description)}}}</CardDescription>')
        w.dedent()
        w.line('</CardHeader>')
    w.line('<CardContent className="flex flex-col gap-4">')
    w.indent()
    for child in node.children:
        emit_node(child, w, ctx)
    w.dedent()
    w.line('</CardContent>')
    w.dedent()
    w.line('</Card>')
    _close_visible_guard(guarded, w)


def emit_node(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    emitter = EMITTERS.get(node.tag)
    if emitter is None:
        w.line(f'{{/* unknown component: {node.tag} ({node.anchor}) */}}')
        return
    emitter(node, w, ctx)


def emit_page(page_ir: PageIR) -> str:
    """生成完整的页面 TSX 文件。"""
    ctx = _PageEmitContext()
    _prepare_bindings(page_ir, ctx)
    body_writer = TsxWriter()

    for root in page_ir.roots:
        emit_node(root, body_writer, ctx)

    w = TsxWriter()
    w.line('/* 由 pyshade 编译器生成 — 请勿手改。 */')
    react_imports: list[str] = []
    if ctx.controlled_inputs or ctx.client_vals:
        react_imports.append('useState')
    if ctx.sensitive_inputs:
        react_imports.append('useRef')
    if react_imports:
        w.line(f'import {{ {", ".join(sorted(react_imports))} }} from "react";')
    w.line()

    shadcn_map: dict[str, str] = {
        'Button': '"@/components/ui/button"',
        'Card': '"@/components/ui/card"',
        'CardContent': '"@/components/ui/card"',
        'CardDescription': '"@/components/ui/card"',
        'CardHeader': '"@/components/ui/card"',
        'CardTitle': '"@/components/ui/card"',
        'Input': '"@/components/ui/input"',
        'Label': '"@/components/ui/label"',
        'Switch': '"@/components/ui/switch"',
    }
    by_module: dict[str, list[str]] = {}
    for imp in sorted(ctx.imports):
        module = shadcn_map.get(imp, f'"@/components/ui/{imp.lower()}"')
        by_module.setdefault(module, []).append(imp)
    for module, names in sorted(by_module.items()):
        w.line(f'import {{ {", ".join(sorted(names))} }} from {module};')

    w.line('import { usePageRuntime } from "@/runtime/page";')
    w.line()
    w.line(f'export function {page_ir.name}() {{')
    w.indent()
    options_parts: list[str] = []
    if ctx.bound_props:
        bound = ', '.join(js_string(p) for p in ctx.bound_props)
        options_parts.append(f'boundProps: [{bound}]')
    if ctx.uses_push:
        options_parts.append('push: true')
    if options_parts:
        w.line(f'const rt = usePageRuntime({{ {", ".join(options_parts)} }});')
    else:
        w.line('const rt = usePageRuntime();')
    w.line()

    for name, val in ctx.client_vals:
        ts_type = _TS_TYPE[val.type]
        w.line(f'const [{name}Value, set{name.capitalize()}Value] = useState<{ts_type}>({js_value(val.default)});')

    for node in ctx.controlled_inputs:
        if node.anchor in ctx.alias:
            continue  # client_bind:与 ClientVal 共用 useState
        var = _var_name(node.anchor)
        is_switch = isinstance(node.component, Switch)
        if is_switch:
            checked = next((p for p in node.props if p.name == 'checked'), None)
            default_val = js_bool(bool(checked.default_value) if checked else False)
            w.line(f'const [{var}Value, set{var.capitalize()}Value] = useState<boolean>({default_val});')
        else:
            value = next((p for p in node.props if p.name == 'value'), None)
            default_val = js_string(str(value.default_value) if value else '')
            w.line(f'const [{var}Value, set{var.capitalize()}Value] = useState<string>({default_val});')

    for node in ctx.sensitive_inputs:
        var = _var_name(node.anchor)
        w.line(f'const {var}Ref = useRef<HTMLInputElement>(null);')

    if ctx.controlled_inputs or ctx.sensitive_inputs or ctx.client_vals:
        w.line()
        controlled_entries = [f'{_var_name(n.anchor)}: {ctx.value_var(n)}' for n in ctx.controlled_inputs]
        client_val_entries = [f'{name}: {name}Value' for name, _val in ctx.client_vals]
        sensitive_entries = [
            f'{_var_name(n.anchor)}: {_var_name(n.anchor)}Ref.current?.value ?? ""' for n in ctx.sensitive_inputs
        ]
        value_union = 'string | boolean'
        if any(val.type in (ExprType.INT, ExprType.FLOAT) for _name, val in ctx.client_vals):
            value_union += ' | number'
        # 无敏感输入时参数未使用,下划线前缀豁免 noUnusedParameters
        param = 'includeSensitive' if sensitive_entries else '_includeSensitive'
        w.line(f'const collectValues = ({param}: boolean): Record<string, {value_union}> => ({{')
        w.indent()
        for entry in controlled_entries:
            w.line(f'{entry},')
        for entry in client_val_entries:
            w.line(f'{entry},')
        if sensitive_entries:
            w.line(f'...(includeSensitive ? {{ {", ".join(sensitive_entries)} }} : {{}}),')
        w.dedent()
        w.line('});')
        w.line()

    w.line('return (')
    w.indent()
    w.line('<main className="flex min-h-svh items-center justify-center p-6">')
    w.indent()

    for line in body_writer.to_string().rstrip('\n').split('\n'):
        w.line(line)

    w.dedent()
    w.line('</main>')
    w.dedent()
    w.line(');')
    w.dedent()
    w.line('}')
    return w.to_string()
