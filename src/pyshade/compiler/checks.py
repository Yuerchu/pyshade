"""编译期校验(设计 §3.5):事件签名、敏感组件断言、命名冲突。"""

from pyshade.compiler.errors import CompileError
from pyshade.compiler.ir import NodeIR, PageIR
from pyshade.components.base import EventSpec
from pyshade.events import validate_handler

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


def check_page_ir(page_ir: PageIR) -> None:
    """对整个页面 IR 做编译期校验;失败抛 CompileError。"""
    seen_anchors: set[str] = set()
    for root in page_ir.roots:
        _check_node(root, page_ir.name, seen_anchors)


def _check_node(node: NodeIR, page_name: str, seen: set[str]) -> None:
    if node.anchor in seen:
        raise CompileError(f"{node.anchor}: anchor 重复(内部错误)")
    seen.add(node.anchor)

    _check_naming(node, page_name)
    _check_sensitive(node)
    _check_event_handlers(node)

    for child in node.children:
        _check_node(child, page_name, seen)


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
