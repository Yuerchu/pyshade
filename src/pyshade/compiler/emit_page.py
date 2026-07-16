"""页面级 TSX 发射器:每页一文件(设计 §3.3 / §3.4)。

每组件一个 emitter 函数(注册表分发);受控 Input → useState + onBlur;
PasswordInput → uncontrolled useRef;plain prop 显式 rt.ov(anchor, prop, 默认值)。

M1 所有权公理落点:expr prop 内联 to_js 产物(不包 rt.ov,服务端 patch 不可达);
client_bind 受控 prop 与 ClientVal 共用 useState(别名);全部客户端所有的
"anchor.prop" 汇入 usePageRuntime({ boundProps }) 供前端过滤误发 patch。
"""

from collections.abc import Callable
from typing import Any, cast

from pydantic import BaseModel

from pyshade.compiler.errors import CompileError
from pyshade.compiler.ir import NodeIR, PageIR, PropInfo, iter_node_irs
from pyshade.compiler.writer import TsxWriter, js_string, js_value
from pyshade.components.base import Component
from pyshade.expr import ClientVal, Expr, ExprType, ItemRef, PropRef
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

SHADCN_MODULES: dict[str, str] = {
    'Alert': '"@/components/ui/alert"',
    'AlertDescription': '"@/components/ui/alert"',
    'AlertTitle': '"@/components/ui/alert"',
    'Badge': '"@/components/ui/badge"',
    'Button': '"@/components/ui/button"',
    'Card': '"@/components/ui/card"',
    'CardContent': '"@/components/ui/card"',
    'CardDescription': '"@/components/ui/card"',
    'CardHeader': '"@/components/ui/card"',
    'CardTitle': '"@/components/ui/card"',
    'Checkbox': '"@/components/ui/checkbox"',
    'Input': '"@/components/ui/input"',
    'Label': '"@/components/ui/label"',
    'Accordion': '"@/components/ui/accordion"',
    'AccordionContent': '"@/components/ui/accordion"',
    'AccordionItem': '"@/components/ui/accordion"',
    'AccordionTrigger': '"@/components/ui/accordion"',
    'AlertDialog': '"@/components/ui/alert-dialog"',
    'AlertDialogAction': '"@/components/ui/alert-dialog"',
    'AlertDialogCancel': '"@/components/ui/alert-dialog"',
    'AlertDialogContent': '"@/components/ui/alert-dialog"',
    'AlertDialogDescription': '"@/components/ui/alert-dialog"',
    'AlertDialogFooter': '"@/components/ui/alert-dialog"',
    'AlertDialogHeader': '"@/components/ui/alert-dialog"',
    'AlertDialogTitle': '"@/components/ui/alert-dialog"',
    'AlertDialogTrigger': '"@/components/ui/alert-dialog"',
    'Dialog': '"@/components/ui/dialog"',
    'DialogContent': '"@/components/ui/dialog"',
    'DialogDescription': '"@/components/ui/dialog"',
    'DialogHeader': '"@/components/ui/dialog"',
    'DialogTitle': '"@/components/ui/dialog"',
    'DialogTrigger': '"@/components/ui/dialog"',
    'Progress': '"@/components/ui/progress"',
    'RadioGroup': '"@/components/ui/radio-group"',
    'RadioGroupItem': '"@/components/ui/radio-group"',
    'ScrollArea': '"@/components/ui/scroll-area"',
    'Select': '"@/components/ui/select"',
    'SelectContent': '"@/components/ui/select"',
    'SelectItem': '"@/components/ui/select"',
    'SelectTrigger': '"@/components/ui/select"',
    'SelectValue': '"@/components/ui/select"',
    'Separator': '"@/components/ui/separator"',
    'Skeleton': '"@/components/ui/skeleton"',
    'Slider': '"@/components/ui/slider"',
    'Switch': '"@/components/ui/switch"',
    'Tabs': '"@/components/ui/tabs"',
    'TabsContent': '"@/components/ui/tabs"',
    'TabsList': '"@/components/ui/tabs"',
    'TabsTrigger': '"@/components/ui/tabs"',
    'Textarea': '"@/components/ui/textarea"',
    'Tooltip': '"@/components/ui/tooltip"',
    'TooltipContent': '"@/components/ui/tooltip"',
    'TooltipProvider': '"@/components/ui/tooltip"',
    'TooltipTrigger': '"@/components/ui/tooltip"',
}
"""shadcn 元件名 → import 模块;emit 与 bundler(extra_components 逃生舱)共用。"""


def register(tag: str) -> Callable[[EmitFn], EmitFn]:
    def decorator(fn: EmitFn) -> EmitFn:
        EMITTERS[tag] = fn
        return fn

    return decorator


class _LoopContext:
    """Each 模板发射期间的循环上下文:item/index 变量名与 key 字段。"""

    __slots__ = ('item_var', 'index_var', 'key_field')

    def __init__(self, item_var: str, index_var: str, key_field: str | None) -> None:
        self.item_var = item_var
        self.index_var = index_var
        self.key_field = key_field


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
        self.no_guard_anchors: set[str] = set()
        """asChild 槽(Dialog trigger / Tooltip 宿主)不发 visible guard(单元素约束)。"""
        self.loop: _LoopContext | None = None
        """Each 模板发射中(§3.3 模板行):plain prop 发字面量,事件 payload 带 item_index。"""
        self.uses_collect_values: bool = False
        """页面存在 submit 消费点才发 collectValues(未使用的声明过不了 noUnusedLocals)。"""
        self.item_models: dict[str, type[BaseModel]] = {}
        """Each 项模型(类名 → 类):页面头部发 `import type { ... } from "../types.gen"`。"""

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
        if prop.binding == 'const':
            # 构建期常量(§3.3 'const' 行):编译期定值,发字面量,patch 不可达
            return js_value(prop.default_value)
        if prop.binding == 'expr':
            return cast('Expr[Any]', prop.default_value).to_js(self.scope)
        if prop.binding == 'server_ref':
            ref = cast('ServerRef[Any]', prop.default_value)
            return f'rt.ov({js_string(ref.target)}, {js_string(ref.field)}, {js_value(ref.default)})'
        if self.loop is not None:
            # 模板内 plain prop 是构建期常量(§3.3):模板 anchor 跨 item 共享,rt.ov 无 per-item 语义
            return js_value(prop.default_value)
        return _ov(node.anchor, prop.name, prop.default_value)


def _var_name(anchor: str) -> str:
    return anchor.split('.')[-1].replace('[', '_').replace(']', '')


def _controlled_default(node: NodeIR) -> object:
    """受控组件 useState 的初始值:受控 prop 的 plain 默认值(client_bind 已走 alias 分支)。"""
    from pyshade.components.base import ControlledMixin, controlled_prop_of

    component = node.component
    assert isinstance(component, ControlledMixin), f'{node.anchor} 不是受控组件'
    prop_name = controlled_prop_of(component)
    prop = next(p for p in node.props if p.name == prop_name)
    return prop.default_value


def _scalar_expr_type(value: object) -> ExprType:
    """受控默认值 → ExprType(bool 先于 int 判定)。"""
    if isinstance(value, bool):
        return ExprType.BOOL
    if isinstance(value, int):
        return ExprType.INT
    if isinstance(value, float):
        return ExprType.FLOAT
    if isinstance(value, str):
        return ExprType.STR
    raise CompileError(f"受控 prop 默认值必须是标量,收到 {type(value).__name__}")


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
            if '.$t[' not in node.anchor:
                # 模板 anchor 不进 boundProps:Update 构造期即拒绝,patch 永远不可能指向模板
                ctx.bound_props.append(f'{node.anchor}.{prop.name}')
            if prop.binding != 'expr':
                continue
            for leaf in cast('Expr[Any]', prop.default_value).refs():
                if leaf in ctx.scope:
                    continue
                if isinstance(leaf, ItemRef):
                    continue  # 循环变量:Each emitter 进入模板时注册 scope(checks 已验归属)
                if isinstance(leaf, PropRef):
                    anchor = anchor_of(leaf.component)
                    base = ctx.alias.get(anchor) or _var_name(anchor)
                    ctx.scope[leaf] = f'{base}Value'
                else:
                    raise CompileError(f"{node.anchor}.{prop.name}: 引用的 ClientVal 未声明为本页面字段")


def _emit_visible_guard(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> bool:
    if node.anchor in ctx.no_guard_anchors:
        return False
    visible_prop = next((p for p in node.props if p.name == 'visible'), None)
    if visible_prop is None:
        return False
    if visible_prop.binding == 'expr':
        js = cast('Expr[Any]', visible_prop.default_value).to_js(ctx.scope)
        w.line(f'{{({js}) && (')
        w.indent()
        return True
    if ctx.loop is not None and visible_prop.binding == 'plain':
        return False  # 模板 plain visible 是构建期常量;checks 已保证其为 True
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


_HEADING_TAGS: dict[int, tuple[str, str]] = {
    1: ('h1', 'scroll-m-20 text-4xl font-extrabold tracking-tight'),
    2: ('h2', 'scroll-m-20 text-3xl font-semibold tracking-tight'),
    3: ('h3', 'scroll-m-20 text-2xl font-semibold tracking-tight'),
    4: ('h4', 'scroll-m-20 text-xl font-semibold tracking-tight'),
}
"""level → (标签, 排版 class);字符串写在编译器源码内,发版 CSS 预编译经 @source 扫描命中。"""


@register('Heading')
def emit_heading(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    guarded = _emit_visible_guard(node, w, ctx)
    level = next(p for p in node.props if p.name == 'level')
    text = next((p for p in node.props if p.name == 'text'), None)
    tag, class_name = _HEADING_TAGS[cast('int', level.default_value)]
    text_js = ctx.prop_js(node, text) if text else js_string('')
    w.line(f'<{tag} className="{class_name}">{{{text_js}}}</{tag}>')
    _close_visible_guard(guarded, w)


@register('Link')
def emit_link(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    guarded = _emit_visible_guard(node, w, ctx)
    text = next(p for p in node.props if p.name == 'text')
    href = next(p for p in node.props if p.name == 'href')
    w.line(
        f'<a href={{{ctx.prop_js(node, href)}}} target="_blank" rel="noreferrer" '
        f'className="font-medium underline underline-offset-4">{{{ctx.prop_js(node, text)}}}</a>'
    )
    _close_visible_guard(guarded, w)


@register('Markdown')
def emit_markdown(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    """编译期 md→HTML(const),dangerouslySetInnerHTML 内联;样式走 typography prose。"""
    from pyshade.compiler._content import render_markdown

    guarded = _emit_visible_guard(node, w, ctx)
    source = next(p for p in node.props if p.name == 'source')
    html = render_markdown(cast('str', source.default_value))
    w.line(
        '<div className="prose prose-neutral dark:prose-invert max-w-none" '
        f'dangerouslySetInnerHTML={{{{ __html: {js_string(html)} }}}} />'
    )
    _close_visible_guard(guarded, w)


@register('CodeBlock')
def emit_code_block(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    """编译期 pygments 高亮(const);.shade-hl 作用域化 token 样式(index.css 手写块)。"""
    from pyshade.compiler._content import highlight_code

    guarded = _emit_visible_guard(node, w, ctx)
    code = next(p for p in node.props if p.name == 'code')
    language = next(p for p in node.props if p.name == 'language')
    html = highlight_code(cast('str', code.default_value), cast('str', language.default_value))
    w.line(f'<pre className="shade-hl"><code dangerouslySetInnerHTML={{{{ __html: {js_string(html)} }}}} /></pre>')
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
    click_nav = next((n for n in node.navigations if n.kind == 'click'), None)
    click_scheme = next((s for s in node.schemes if s.kind == 'click'), None)

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
        if ctx.loop is not None:
            # 模板事件共享 handlerId,payload 携带 item_index(+item_key)定位数据
            payload_parts = [f'item_index: {ctx.loop.index_var}']
            if ctx.loop.key_field is not None:
                payload_parts.append(f'item_key: {ctx.loop.item_var}.{ctx.loop.key_field}')
            attrs.append(f'onClick={{() => rt.fire({hid}, {{ {", ".join(payload_parts)} }})}}')
        elif is_submit:
            ctx.uses_collect_values = True
            attrs.append(f'onClick={{() => rt.fire({hid}, {{ values: collectValues(true) }})}}')
        else:
            attrs.append(f'onClick={{() => rt.fire({hid}, {{}})}}')
    elif click_nav:
        attrs.append(f'onClick={{() => rt.navigate({js_string(click_nav.target_page)})}}')
    elif click_scheme:
        attrs.append(f'onClick={{() => rt.setColorScheme({js_string(click_scheme.mode)})}}')

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


@register('Badge')
def emit_badge(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Badge')
    guarded = _emit_visible_guard(node, w, ctx)
    variant = next((p for p in node.props if p.name == 'variant'), None)
    text = next((p for p in node.props if p.name == 'text'), None)
    attrs = f' variant={{{ctx.prop_js(node, variant)}}}' if variant else ''
    text_js = ctx.prop_js(node, text) if text else js_string('')
    w.line(f'<Badge{attrs}>{{{text_js}}}</Badge>')
    _close_visible_guard(guarded, w)


@register('Alert')
def emit_alert(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Alert')
    ctx.imports.add('AlertTitle')
    guarded = _emit_visible_guard(node, w, ctx)
    variant = next((p for p in node.props if p.name == 'variant'), None)
    title = next((p for p in node.props if p.name == 'title'), None)
    description = _opt_prop(node, 'description')

    attrs = f' variant={{{ctx.prop_js(node, variant)}}}' if variant else ''
    w.line(f'<Alert{attrs}>')
    w.indent()
    title_js = ctx.prop_js(node, title) if title else js_string('')
    w.line(f'<AlertTitle>{{{title_js}}}</AlertTitle>')
    if description:
        ctx.imports.add('AlertDescription')
        w.line(f'<AlertDescription>{{{ctx.prop_js(node, description)}}}</AlertDescription>')
    w.dedent()
    w.line('</Alert>')
    _close_visible_guard(guarded, w)


@register('Separator')
def emit_separator(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Separator')
    guarded = _emit_visible_guard(node, w, ctx)
    orientation = next((p for p in node.props if p.name == 'orientation'), None)
    attrs = f' orientation={{{ctx.prop_js(node, orientation)}}}' if orientation else ''
    w.line(f'<Separator{attrs} />')
    _close_visible_guard(guarded, w)


@register('Skeleton')
def emit_skeleton(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Skeleton')
    guarded = _emit_visible_guard(node, w, ctx)
    width = _opt_prop(node, 'width')
    height = _opt_prop(node, 'height')
    if width or height:
        parts: list[str] = []
        if width:
            parts.append(f'width: {js_string(str(width.default_value))}')
        if height:
            parts.append(f'height: {js_string(str(height.default_value))}')
        w.line(f'<Skeleton style={{{{ {", ".join(parts)} }}}} />')
    else:
        w.line('<Skeleton className="h-4 w-full" />')
    _close_visible_guard(guarded, w)


@register('Progress')
def emit_progress(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Progress')
    guarded = _emit_visible_guard(node, w, ctx)
    value = next((p for p in node.props if p.name == 'value'), None)
    value_js = ctx.prop_js(node, value) if value else '0'
    w.line(f'<Progress value={{{value_js}}} />')
    _close_visible_guard(guarded, w)


@register('Textarea')
def emit_textarea(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Textarea')
    ctx.imports.add('Label')
    ctx.add_controlled(node)
    var = ctx.value_var(node)
    setter = ctx.setter(node)
    guarded = _emit_visible_guard(node, w, ctx)

    label = _opt_prop(node, 'label')
    placeholder = _opt_prop(node, 'placeholder')
    rows = next((p for p in node.props if p.name == 'rows'), None)
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    change_event = next((e for e in node.events if e.kind == 'change'), None)

    w.line('<div className="grid gap-2">')
    w.indent()
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{ctx.prop_js(node, label)}}}</Label>')
    attrs: list[str] = [f'id={js_string(node.anchor)}']
    if placeholder:
        attrs.append(f'placeholder={{{ctx.prop_js(node, placeholder)}}}')
    if rows:
        attrs.append(f'rows={{{ctx.prop_js(node, rows)}}}')
    if disabled:
        attrs.append(f'disabled={{{ctx.prop_js(node, disabled)}}}')
    attrs.append(f'value={{{var}}}')
    attrs.append(f'onChange={{(e) => {setter}(e.target.value)}}')
    if change_event:
        attrs.append(f'onBlur={{() => rt.fire({js_string(change_event.handler_id)}, {{ value: {var} }})}}')
    w.line(f'<Textarea {" ".join(attrs)} />')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


@register('Checkbox')
def emit_checkbox(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Checkbox')
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
    # radix indeterminate 三态按 checked === true 归一化(M2 不支持三态)
    change_parts: list[str] = [f'{setter}(checked === true)']
    if change_event:
        change_parts.append(f'rt.fire({js_string(change_event.handler_id)}, {{ value: checked === true }})')
    attrs.append(f'onCheckedChange={{(checked) => {{ {"; ".join(change_parts)} }}}}')
    w.line(f'<Checkbox {" ".join(attrs)} />')
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{ctx.prop_js(node, label)}}}</Label>')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


_OPTION_TS_TYPE = '{ value: string; label: string }[]'


@register('Select')
def emit_select(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    for name in ('Select', 'SelectContent', 'SelectItem', 'SelectTrigger', 'SelectValue', 'Label'):
        ctx.imports.add(name)
    ctx.add_controlled(node)
    var = ctx.value_var(node)
    setter = ctx.setter(node)
    guarded = _emit_visible_guard(node, w, ctx)

    label = _opt_prop(node, 'label')
    placeholder = _opt_prop(node, 'placeholder')
    options = next(p for p in node.props if p.name == 'options')
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    change_event = next((e for e in node.events if e.kind == 'change'), None)

    change_parts = [f'{setter}(v)']
    if change_event:
        change_parts.append(f'rt.fire({js_string(change_event.handler_id)}, {{ value: v }})')

    w.line('<div className="grid gap-2">')
    w.indent()
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{ctx.prop_js(node, label)}}}</Label>')
    root_attrs = [f'value={{{var}}}', f'onValueChange={{(v) => {{ {"; ".join(change_parts)} }}}}']
    if disabled:
        root_attrs.append(f'disabled={{{ctx.prop_js(node, disabled)}}}')
    w.line(f'<Select {" ".join(root_attrs)}>')
    w.indent()
    w.line(f'<SelectTrigger id={js_string(node.anchor)}>')
    w.indent()
    placeholder_attr = f' placeholder={{{ctx.prop_js(node, placeholder)}}}' if placeholder else ''
    w.line(f'<SelectValue{placeholder_attr} />')
    w.dedent()
    w.line('</SelectTrigger>')
    w.line('<SelectContent>')
    w.indent()
    options_js = f'rt.ov<{_OPTION_TS_TYPE}>({js_string(node.anchor)}, "options", {js_value(options.default_value)})'
    w.line(f'{{{options_js}.map((o) => (')
    w.indent()
    w.line('<SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>')
    w.dedent()
    w.line('))}')
    w.dedent()
    w.line('</SelectContent>')
    w.dedent()
    w.line('</Select>')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


@register('RadioGroup')
def emit_radio_group(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    for name in ('RadioGroup', 'RadioGroupItem', 'Label'):
        ctx.imports.add(name)
    ctx.add_controlled(node)
    var = ctx.value_var(node)
    setter = ctx.setter(node)
    guarded = _emit_visible_guard(node, w, ctx)

    label = _opt_prop(node, 'label')
    options = next(p for p in node.props if p.name == 'options')
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    change_event = next((e for e in node.events if e.kind == 'change'), None)

    change_parts = [f'{setter}(v)']
    if change_event:
        change_parts.append(f'rt.fire({js_string(change_event.handler_id)}, {{ value: v }})')

    w.line('<div className="grid gap-2">')
    w.indent()
    if label:
        w.line(f'<Label>{{{ctx.prop_js(node, label)}}}</Label>')
    root_attrs = [f'value={{{var}}}', f'onValueChange={{(v) => {{ {"; ".join(change_parts)} }}}}']
    if disabled:
        root_attrs.append(f'disabled={{{ctx.prop_js(node, disabled)}}}')
    w.line(f'<RadioGroup {" ".join(root_attrs)}>')
    w.indent()
    options_js = f'rt.ov<{_OPTION_TS_TYPE}>({js_string(node.anchor)}, "options", {js_value(options.default_value)})'
    w.line(f'{{{options_js}.map((o) => (')
    w.indent()
    w.line('<div key={o.value} className="flex items-center gap-2">')
    w.indent()
    w.line(f'<RadioGroupItem id={{{js_string(node.anchor)} + "-" + o.value}} value={{o.value}} />')
    w.line(f'<Label htmlFor={{{js_string(node.anchor)} + "-" + o.value}}>{{o.label}}</Label>')
    w.dedent()
    w.line('</div>')
    w.dedent()
    w.line('))}')
    w.dedent()
    w.line('</RadioGroup>')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


@register('Slider')
def emit_slider(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('Slider')
    ctx.imports.add('Label')
    ctx.add_controlled(node)
    var = ctx.value_var(node)
    setter = ctx.setter(node)
    guarded = _emit_visible_guard(node, w, ctx)

    label = _opt_prop(node, 'label')
    disabled = next((p for p in node.props if p.name == 'disabled'), None)
    change_event = next((e for e in node.events if e.kind == 'change'), None)

    w.line('<div className="grid gap-2">')
    w.indent()
    if label:
        w.line(f'<Label htmlFor={js_string(node.anchor)}>{{{ctx.prop_js(node, label)}}}</Label>')
    attrs: list[str] = [f'id={js_string(node.anchor)}']
    for bound in ('min', 'max', 'step'):
        prop = next((p for p in node.props if p.name == bound), None)
        if prop:
            attrs.append(f'{bound}={{{ctx.prop_js(node, prop)}}}')
    if disabled:
        attrs.append(f'disabled={{{ctx.prop_js(node, disabled)}}}')
    # 拖动仅本地 state,松手才跨界(0-keystroke-IPC)
    attrs.append(f'value={{[{var}]}}')
    attrs.append(f'onValueChange={{([v]) => {setter}(v)}}')
    if change_event:
        attrs.append(f'onValueCommit={{([v]) => rt.fire({js_string(change_event.handler_id)}, {{ value: v }})}}')
    w.line(f'<Slider {" ".join(attrs)} />')
    w.dedent()
    w.line('</div>')
    _close_visible_guard(guarded, w)


def _find_trigger_child(node: NodeIR) -> NodeIR | None:
    """按实例同一性从 children 里切出 trigger 槽的 IR 节点。"""
    trigger: object = getattr(node.component, 'trigger', None)
    if not isinstance(trigger, Component):
        return None
    trigger_anchor = anchor_of(trigger)
    return next((child for child in node.children if child.anchor == trigger_anchor), None)


def _dialog_open_attrs(node: NodeIR, ctx: _PageEmitContext) -> list[str]:
    """open 的两档形态:client_bind → 受控;plain → defaultOpen(仅初始值)。"""
    open_prop = next(p for p in node.props if p.name == 'open')
    if open_prop.binding == 'client_bind':
        ctx.add_controlled(node)
        var = ctx.value_var(node)
        setter = ctx.setter(node)
        return [f'open={{{var}}}', f'onOpenChange={{{setter}}}']
    if open_prop.default_value is True:
        return ['defaultOpen']
    return []


@register('Dialog')
def emit_dialog(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    for name in ('Dialog', 'DialogContent'):
        ctx.imports.add(name)
    guarded = _emit_visible_guard(node, w, ctx)

    title = _opt_prop(node, 'title')
    description = _opt_prop(node, 'description')
    trigger_node = _find_trigger_child(node)

    attrs = _dialog_open_attrs(node, ctx)
    w.line(f'<Dialog{" " + " ".join(attrs) if attrs else ""}>')
    w.indent()
    if trigger_node is not None:
        ctx.imports.add('DialogTrigger')
        ctx.no_guard_anchors.add(trigger_node.anchor)
        w.line('<DialogTrigger asChild>')
        w.indent()
        emit_node(trigger_node, w, ctx)
        w.dedent()
        w.line('</DialogTrigger>')
    w.line('<DialogContent>')
    w.indent()
    if title or description:
        ctx.imports.add('DialogHeader')
        w.line('<DialogHeader>')
        w.indent()
        if title:
            ctx.imports.add('DialogTitle')
            w.line(f'<DialogTitle>{{{ctx.prop_js(node, title)}}}</DialogTitle>')
        if description:
            ctx.imports.add('DialogDescription')
            w.line(f'<DialogDescription>{{{ctx.prop_js(node, description)}}}</DialogDescription>')
        w.dedent()
        w.line('</DialogHeader>')
    for child in node.children:
        if trigger_node is not None and child.anchor == trigger_node.anchor:
            continue
        emit_node(child, w, ctx)
    w.dedent()
    w.line('</DialogContent>')
    w.dedent()
    w.line('</Dialog>')
    _close_visible_guard(guarded, w)


@register('AlertDialog')
def emit_alert_dialog(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    for name in (
        'AlertDialog',
        'AlertDialogAction',
        'AlertDialogCancel',
        'AlertDialogContent',
        'AlertDialogFooter',
        'AlertDialogHeader',
        'AlertDialogTitle',
    ):
        ctx.imports.add(name)
    guarded = _emit_visible_guard(node, w, ctx)

    title = next((p for p in node.props if p.name == 'title'), None)
    description = _opt_prop(node, 'description')
    confirm_text = next((p for p in node.props if p.name == 'confirm_text'), None)
    cancel_text = next((p for p in node.props if p.name == 'cancel_text'), None)
    destructive = next((p for p in node.props if p.name == 'destructive'), None)
    confirm_event = next((e for e in node.events if e.field_name == 'on_confirm'), None)
    cancel_event = next((e for e in node.events if e.field_name == 'on_cancel'), None)
    trigger_node = _find_trigger_child(node)

    attrs = _dialog_open_attrs(node, ctx)
    w.line(f'<AlertDialog{" " + " ".join(attrs) if attrs else ""}>')
    w.indent()
    if trigger_node is not None:
        ctx.imports.add('AlertDialogTrigger')
        ctx.no_guard_anchors.add(trigger_node.anchor)
        w.line('<AlertDialogTrigger asChild>')
        w.indent()
        emit_node(trigger_node, w, ctx)
        w.dedent()
        w.line('</AlertDialogTrigger>')
    w.line('<AlertDialogContent>')
    w.indent()
    w.line('<AlertDialogHeader>')
    w.indent()
    title_js = ctx.prop_js(node, title) if title else js_string('')
    w.line(f'<AlertDialogTitle>{{{title_js}}}</AlertDialogTitle>')
    if description:
        ctx.imports.add('AlertDialogDescription')
        w.line(f'<AlertDialogDescription>{{{ctx.prop_js(node, description)}}}</AlertDialogDescription>')
    w.dedent()
    w.line('</AlertDialogHeader>')
    w.line('<AlertDialogFooter>')
    w.indent()
    cancel_attrs = ''
    if cancel_event:
        cancel_attrs = f' onClick={{() => rt.fire({js_string(cancel_event.handler_id)}, {{}})}}'
    cancel_js = ctx.prop_js(node, cancel_text) if cancel_text else js_string('取消')
    w.line(f'<AlertDialogCancel{cancel_attrs}>{{{cancel_js}}}</AlertDialogCancel>')
    action_attrs: list[str] = []
    if destructive and destructive.default_value is True:
        action_attrs.append('className="bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90"')
    if confirm_event:
        action_attrs.append(f'onClick={{() => rt.fire({js_string(confirm_event.handler_id)}, {{}})}}')
    confirm_js = ctx.prop_js(node, confirm_text) if confirm_text else js_string('确认')
    action_str = f' {" ".join(action_attrs)}' if action_attrs else ''
    w.line(f'<AlertDialogAction{action_str}>{{{confirm_js}}}</AlertDialogAction>')
    w.dedent()
    w.line('</AlertDialogFooter>')
    w.dedent()
    w.line('</AlertDialogContent>')
    w.dedent()
    w.line('</AlertDialog>')
    _close_visible_guard(guarded, w)


@register('Tooltip')
def emit_tooltip(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    for name in ('Tooltip', 'TooltipContent', 'TooltipProvider', 'TooltipTrigger'):
        ctx.imports.add(name)
    guarded = _emit_visible_guard(node, w, ctx)

    text = next((p for p in node.props if p.name == 'text'), None)
    side = next((p for p in node.props if p.name == 'side'), None)

    w.line('<TooltipProvider>')
    w.indent()
    w.line('<Tooltip>')
    w.indent()
    w.line('<TooltipTrigger asChild>')
    w.indent()
    for child in node.children:
        ctx.no_guard_anchors.add(child.anchor)
        emit_node(child, w, ctx)
    w.dedent()
    w.line('</TooltipTrigger>')
    side_attr = f' side={{{ctx.prop_js(node, side)}}}' if side else ''
    text_js = ctx.prop_js(node, text) if text else js_string('')
    w.line(f'<TooltipContent{side_attr}>{{{text_js}}}</TooltipContent>')
    w.dedent()
    w.line('</Tooltip>')
    w.dedent()
    w.line('</TooltipProvider>')
    _close_visible_guard(guarded, w)


@register('Tabs')
def emit_tabs(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    for name in ('Tabs', 'TabsContent', 'TabsList', 'TabsTrigger'):
        ctx.imports.add(name)
    guarded = _emit_visible_guard(node, w, ctx)

    value_prop = next(p for p in node.props if p.name == 'value')
    change_event = next((e for e in node.events if e.kind == 'change'), None)
    items = node.children

    attrs: list[str] = []
    if value_prop.binding == 'client_bind':
        ctx.add_controlled(node)
        var = ctx.value_var(node)
        setter = ctx.setter(node)
        change_parts = [f'{setter}(v)']
        if change_event:
            change_parts.append(f'rt.fire({js_string(change_event.handler_id)}, {{ value: v }})')
        attrs.append(f'value={{{var}}}')
        attrs.append(f'onValueChange={{(v) => {{ {"; ".join(change_parts)} }}}}')
    else:
        default = value_prop.default_value
        if not (isinstance(default, str) and default) and items:
            default = getattr(items[0].component, 'value', '')
        attrs.append(f'defaultValue={js_string(str(default))}')
        if change_event:
            attrs.append(f'onValueChange={{(v) => rt.fire({js_string(change_event.handler_id)}, {{ value: v }})}}')

    w.line(f'<Tabs {" ".join(attrs)}>')
    w.indent()
    w.line('<TabsList>')
    w.indent()
    for item in items:
        item_guarded = _emit_visible_guard(item, w, ctx)
        item_value = js_string(str(getattr(item.component, 'value', '')))
        label = next((p for p in item.props if p.name == 'label'), None)
        label_js = f'rt.ov({js_string(item.anchor)}, "label", {js_value(label.default_value if label else "")})'
        w.line(f'<TabsTrigger value={item_value}>{{{label_js}}}</TabsTrigger>')
        _close_visible_guard(item_guarded, w)
    w.dedent()
    w.line('</TabsList>')
    for item in items:
        item_guarded = _emit_visible_guard(item, w, ctx)
        item_value = js_string(str(getattr(item.component, 'value', '')))
        w.line(f'<TabsContent value={item_value} className="flex flex-col gap-4">')
        w.indent()
        for child in item.children:
            emit_node(child, w, ctx)
        w.dedent()
        w.line('</TabsContent>')
        _close_visible_guard(item_guarded, w)
    w.dedent()
    w.line('</Tabs>')
    _close_visible_guard(guarded, w)


@register('TabItem')
def emit_tab_item(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    raise CompileError(f"{node.anchor}: TabItem 只能作为 Tabs 的直接子组件(不应独立发射)")


@register('Accordion')
def emit_accordion(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    for name in ('Accordion', 'AccordionContent', 'AccordionItem', 'AccordionTrigger'):
        ctx.imports.add(name)
    guarded = _emit_visible_guard(node, w, ctx)

    multiple = next((p for p in node.props if p.name == 'multiple'), None)
    is_multiple = multiple is not None and multiple.default_value is True
    type_attr = 'type="multiple"' if is_multiple else 'type="single" collapsible'

    w.line(f'<Accordion {type_attr}>')
    w.indent()
    for item in node.children:
        item_guarded = _emit_visible_guard(item, w, ctx)
        item_value = js_string(str(getattr(item.component, 'value', '')))
        title = next((p for p in item.props if p.name == 'title'), None)
        title_js = ctx.prop_js(item, title) if title else js_string('')
        w.line(f'<AccordionItem value={item_value}>')
        w.indent()
        w.line(f'<AccordionTrigger>{{{title_js}}}</AccordionTrigger>')
        w.line('<AccordionContent className="flex flex-col gap-4">')
        w.indent()
        for child in item.children:
            emit_node(child, w, ctx)
        w.dedent()
        w.line('</AccordionContent>')
        w.dedent()
        w.line('</AccordionItem>')
        _close_visible_guard(item_guarded, w)
    w.dedent()
    w.line('</Accordion>')
    _close_visible_guard(guarded, w)


@register('AccordionItem')
def emit_accordion_item(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    raise CompileError(f"{node.anchor}: AccordionItem 只能作为 Accordion 的直接子组件(不应独立发射)")


@register('ScrollArea')
def emit_scroll_area(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    ctx.imports.add('ScrollArea')
    guarded = _emit_visible_guard(node, w, ctx)
    height = next((p for p in node.props if p.name == 'height'), None)
    height_js = js_string(str(height.default_value)) if height else js_string('16rem')
    w.line(f'<ScrollArea style={{{{ height: {height_js} }}}} className="rounded-md border">')
    w.indent()
    w.line('<div className="flex flex-col gap-4 p-4">')
    w.indent()
    for child in node.children:
        emit_node(child, w, ctx)
    w.dedent()
    w.line('</div>')
    w.dedent()
    w.line('</ScrollArea>')
    _close_visible_guard(guarded, w)


@register('Each')
def emit_each(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    """列表渲染:`items.map((xItem: T, xIndex) => <Fragment key={...}>模板</Fragment>)`。

    rt.ov 显式标注 `<T[]>`:空列表 fallback 会推成 never[],必须显式。
    """
    from pyshade.components.each import Each, item_model_of, item_scalar_type_of, iter_item_refs

    each = cast('Each', node.component)
    # visible guard 并进同一个 JSX 表达式(`{guard && items.map(...)}`):
    # 复用 _emit_visible_guard 的 `{... && (` 包裹会让 map 的花括号变成非法嵌套
    visible_prop = next(p for p in node.props if p.name == 'visible')
    guard_js: str | None = None
    if visible_prop.binding == 'expr':
        guard_js = f'({cast("Expr[Any]", visible_prop.default_value).to_js(ctx.scope)})'
    elif visible_prop.binding == 'server_ref' or visible_prop.default_value is True:
        guard_js = ctx.prop_js(node, visible_prop)

    items_prop = next(p for p in node.props if p.name == 'items')
    ref = cast('ServerRef[Any]', items_prop.default_value)
    var = _var_name(node.anchor)
    item_var, index_var = f'{var}Item', f'{var}Index'

    model = item_model_of(each)
    if model is not None:
        item_ts = model.__name__
        ctx.item_models[item_ts] = model
    else:
        scalar = item_scalar_type_of(each)
        assert scalar is not None
        item_ts = _TS_TYPE[scalar]

    for item_ref in iter_item_refs(each):
        ctx.scope[item_ref] = item_var if item_ref.field == '' else f'{item_var}.{item_ref.field}'

    items_js = f'rt.ov<{item_ts}[]>({js_string(ref.target)}, {js_string(ref.field)}, {js_value(ref.default)})'
    key_js = index_var if each.key is None else f'{item_var}.{each.key}'
    prefix = f'{guard_js} && ' if guard_js is not None else ''
    w.line(f'{{{prefix}{items_js}.map(({item_var}: {item_ts}, {index_var}: number) => (')
    w.indent()
    w.line(f'<Fragment key={{{key_js}}}>')
    w.indent()
    ctx.loop = _LoopContext(item_var, index_var, each.key)
    try:
        for child in node.children:
            emit_node(child, w, ctx)
    finally:
        ctx.loop = None
    w.dedent()
    w.line('</Fragment>')
    w.dedent()
    w.line('))}')


def emit_node(node: NodeIR, w: TsxWriter, ctx: _PageEmitContext) -> None:
    emitter = EMITTERS.get(node.tag)
    if emitter is None:
        w.line(f'{{/* unknown component: {node.tag} ({node.anchor}) */}}')
        return
    emitter(node, w, ctx)


def page_binding_summary(page_ir: PageIR) -> tuple[list[str], bool]:
    """页面的 (boundProps, 是否需要 push):emit_app 聚合到 App 级 Provider 用。"""
    ctx = _PageEmitContext()
    _prepare_bindings(page_ir, ctx)
    return ctx.bound_props, ctx.uses_push


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
    if any(node.tag == 'Each' for node in iter_node_irs(page_ir)):
        react_imports.append('Fragment')
    if ctx.controlled_inputs or ctx.client_vals:
        react_imports.append('useState')
    if ctx.sensitive_inputs:
        react_imports.append('useRef')
    if react_imports:
        w.line(f'import {{ {", ".join(sorted(react_imports))} }} from "react";')
    w.line()

    by_module: dict[str, list[str]] = {}
    for imp in sorted(ctx.imports):
        module = SHADCN_MODULES.get(imp, f'"@/components/ui/{imp.lower()}"')
        by_module.setdefault(module, []).append(imp)
    for module, names in sorted(by_module.items()):
        w.line(f'import {{ {", ".join(sorted(names))} }} from {module};')

    w.line('import { usePageRuntime } from "@/runtime/page";')
    if ctx.item_models:
        w.line(f'import type {{ {", ".join(sorted(ctx.item_models))} }} from "../types.gen";')
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
        default_value = _controlled_default(node)
        ts_type = _TS_TYPE[_scalar_expr_type(default_value)]
        w.line(f'const [{var}Value, set{var.capitalize()}Value] = useState<{ts_type}>({js_value(default_value)});')

    for node in ctx.sensitive_inputs:
        var = _var_name(node.anchor)
        w.line(f'const {var}Ref = useRef<HTMLInputElement>(null);')

    if ctx.uses_collect_values:
        w.line()
        controlled_entries = [f'{_var_name(n.anchor)}: {ctx.value_var(n)}' for n in ctx.controlled_inputs]
        client_val_entries = [f'{name}: {name}Value' for name, _val in ctx.client_vals]
        sensitive_entries = [
            f'{_var_name(n.anchor)}: {_var_name(n.anchor)}Ref.current?.value ?? ""' for n in ctx.sensitive_inputs
        ]
        numeric = (ExprType.INT, ExprType.FLOAT)
        has_numeric_client_val = any(val.type in numeric for _name, val in ctx.client_vals)
        has_numeric_controlled = any(
            node.anchor not in ctx.alias and _scalar_expr_type(_controlled_default(node)) in numeric
            for node in ctx.controlled_inputs
        )
        value_union = 'string | boolean'
        if has_numeric_client_val or has_numeric_controlled:
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
