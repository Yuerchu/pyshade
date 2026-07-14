"""页面级 TSX 发射器:每页一文件(设计 §3.3 / §3.4)。

每组件一个 emitter 函数(注册表分发);受控 Input → useState + onBlur;
PasswordInput → uncontrolled useRef;每个 prop 显式 rt.ov(anchor, prop, 默认值)。
"""

from collections.abc import Callable

from pyshade.compiler.ir import NodeIR, PageIR
from pyshade.compiler.writer import TsxWriter, js_bool, js_string, js_value
from pyshade.components.switch import Switch

EmitFn = Callable[[NodeIR, TsxWriter, '_PageEmitContext'], None]

EMITTERS: dict[str, EmitFn] = {}


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

    def add_controlled(self, node: NodeIR) -> None:
        self.controlled_inputs.append(node)

    def add_sensitive(self, node: NodeIR) -> None:
        self.sensitive_inputs.append(node)


def _var_name(anchor: str) -> str:
    return anchor.split('.')[-1].replace('[', '_').replace(']', '')


def _ov(anchor: str, prop: str, default: object) -> str:
    return f'rt.ov({js_string(anchor)}, {js_string(prop)}, {js_value(default)})'


def _emit_visible_guard(node: NodeIR, w: TsxWriter) -> tuple[bool, bool]:
    visible_prop = next((p for p in node.props if p.name == 'visible'), None)
    if visible_prop is not None and visible_prop.default_value is True:
        w.line(f'{{{_ov(node.anchor, "visible", True)} && (')
        w.indent()
        return True, True
    return False, False


def _close_visible_guard(guarded: bool, w: TsxWriter) -> None:
    if guarded:
        w.dedent()
        w.line(')}')


@register('Text')
def emit_text(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    guarded, _ = _emit_visible_guard(node, w)
    muted = next((p for p in node.props if p.name == 'muted'), None)
    class_name = ' className="text-muted-foreground"' if muted and muted.default_value else ''
    w.line(f'<p{class_name}>{{{_ov(node.anchor, "text", "")}}}</p>')
    _close_visible_guard(guarded, w)


@register('Button')
def emit_button(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Button')
    guarded, _ = _emit_visible_guard(node, w)
    variant = next((p for p in node.props if p.name == 'variant'), None)
    size = next((p for p in node.props if p.name == 'size'), None)
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    text = next((p for p in node.props if p.name == 'text'), None)
    submit = next((p for p in node.props if p.name == 'submit'), None)
    click_event = next((e for e in node.events if e.kind == 'click'), None)

    is_submit = submit is not None and submit.default_value is True
    attrs: list[str] = []
    if variant:
        attrs.append(f'variant={{{_ov(node.anchor, "variant", variant.default_value)}}}')
    if size:
        attrs.append(f'size={{{_ov(node.anchor, "size", size.default_value)}}}')
    if disabled:
        attrs.append(f'disabled={{{_ov(node.anchor, "disabled", disabled.default_value)}}}')
    if click_event:
        hid = js_string(click_event.handler_id)
        if is_submit:
            attrs.append(f'onClick={{() => rt.fire({hid}, {{ values: collectValues(true) }})}}')
        else:
            attrs.append(f'onClick={{() => rt.fire({hid}, {{}})}}')

    text_val = _ov(node.anchor, 'text', text.default_value if text else '')
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
    var = _var_name(node.anchor)
    guarded, _ = _emit_visible_guard(node, w)

    label = next((p for p in node.props if p.name == 'label'), None)
    placeholder = next((p for p in node.props if p.name == 'placeholder'), None)
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    change_event = next((e for e in node.events if e.kind == 'change'), None)

    w.line('<div className="grid gap-2">')
    w.indent()
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{_ov(node.anchor, "label", label.default_value)}}}</Label>')
    attrs: list[str] = [f'id={js_string(node.anchor)}']
    if placeholder:
        attrs.append(f'placeholder={{{_ov(node.anchor, "placeholder", placeholder.default_value)}}}')
    if disabled:
        attrs.append(f'disabled={{{_ov(node.anchor, "disabled", disabled.default_value)}}}')
    attrs.append(f'value={{{var}Value}}')
    attrs.append(f'onChange={{(e) => set{var.capitalize()}Value(e.target.value)}}')
    if change_event:
        attrs.append(f'onBlur={{() => rt.fire({js_string(change_event.handler_id)}, {{ value: {var}Value }})}}')
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
    guarded, _ = _emit_visible_guard(node, w)

    label = next((p for p in node.props if p.name == 'label'), None)
    placeholder = next((p for p in node.props if p.name == 'placeholder'), None)
    disabled = next((p for p in node.props if p.name == 'disabled'), None)

    w.line('<div className="grid gap-2">')
    w.indent()
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{_ov(node.anchor, "label", label.default_value)}}}</Label>')
    attrs: list[str] = [
        f'id={js_string(node.anchor)}',
        'type="password"',
        'autoComplete="current-password"',
        f'ref={{{var}Ref}}',
    ]
    if placeholder:
        attrs.append(f'placeholder={{{_ov(node.anchor, "placeholder", placeholder.default_value)}}}')
    if disabled:
        attrs.append(f'disabled={{{_ov(node.anchor, "disabled", disabled.default_value)}}}')
    w.line(f'<Input {" ".join(attrs)} />')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


@register('Switch')
def emit_switch(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Switch')
    ctx.imports.add('Label')
    ctx.add_controlled(node)
    var = _var_name(node.anchor)
    guarded, _ = _emit_visible_guard(node, w)

    label = next((p for p in node.props if p.name == 'label'), None)
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    change_event = next((e for e in node.events if e.kind == 'change'), None)

    w.line('<div className="flex items-center gap-2">')
    w.indent()

    attrs: list[str] = [
        f'id={js_string(node.anchor)}',
        f'checked={{{var}Value}}',
    ]
    if disabled:
        attrs.append(f'disabled={{{_ov(node.anchor, "disabled", disabled.default_value)}}}')

    change_parts: list[str] = [f'set{var.capitalize()}Value(checked)']
    if change_event:
        change_parts.append(f'rt.fire({js_string(change_event.handler_id)}, {{ value: checked }})')
    change_body = '; '.join(change_parts)
    attrs.append(f'onCheckedChange={{(checked) => {{ {change_body} }}}}')

    w.line(f'<Switch {" ".join(attrs)} />')
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{_ov(node.anchor, "label", label.default_value)}}}</Label>')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


@register('Card')
def emit_card(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Card')
    ctx.imports.add('CardContent')
    guarded, _ = _emit_visible_guard(node, w)

    title = next((p for p in node.props if p.name == 'title'), None)
    description = next((p for p in node.props if p.name == 'description'), None)

    w.line('<Card className="w-full max-w-sm">')
    w.indent()
    if title or description:
        ctx.imports.add('CardHeader')
        w.line('<CardHeader>')
        w.indent()
        if title:
            ctx.imports.add('CardTitle')
            w.line(f'<CardTitle>{{{_ov(node.anchor, "title", title.default_value)}}}</CardTitle>')
        if description:
            ctx.imports.add('CardDescription')
            desc_ov = _ov(node.anchor, 'description', description.default_value)
            w.line(f'<CardDescription>{{{desc_ov}}}</CardDescription>')
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
    body_writer = TsxWriter()

    for root in page_ir.roots:
        emit_node(root, body_writer, ctx)

    w = TsxWriter()
    w.line('/* 由 pyshade 编译器生成 — 请勿手改。 */')
    react_imports: list[str] = []
    if ctx.controlled_inputs:
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
    w.line('const rt = usePageRuntime();')
    w.line()

    for node in ctx.controlled_inputs:
        var = _var_name(node.anchor)
        is_switch = isinstance(node.component, Switch)
        if is_switch:
            checked = next((p for p in node.props if p.name == 'checked'), None)
            default_val = js_bool(checked.default_value if checked else False)
            w.line(f'const [{var}Value, set{var.capitalize()}Value] = useState<boolean>({default_val});')
        else:
            value = next((p for p in node.props if p.name == 'value'), None)
            default_val = js_string(value.default_value if value else '')
            w.line(f'const [{var}Value, set{var.capitalize()}Value] = useState<string>({default_val});')

    for node in ctx.sensitive_inputs:
        var = _var_name(node.anchor)
        w.line(f'const {var}Ref = useRef<HTMLInputElement>(null);')

    if ctx.controlled_inputs or ctx.sensitive_inputs:
        w.line()
        controlled_entries = [f'{_var_name(n.anchor)}: {_var_name(n.anchor)}Value' for n in ctx.controlled_inputs]
        sensitive_entries = [
            f'{_var_name(n.anchor)}: {_var_name(n.anchor)}Ref.current?.value ?? ""' for n in ctx.sensitive_inputs
        ]
        w.line('const collectValues = (includeSensitive: boolean): Record<string, string | boolean> => ({')
        w.indent()
        for entry in controlled_entries:
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
