"""app.gen.tsx + manifest.json 发射(设计 §3.4;M2 Phase 5 路由)。

app.gen.tsx 只聚合参数与页面表,骨架是手写 runtime(frontend/src/runtime/app.tsx):
boundProps 全页聚合、push 任一页需要即开、初始页 = pages[0]。
"""

import json

from pyshade.compiler.emit_page import page_binding_summary
from pyshade.compiler.ir import NodeIR, PageIR, iter_node_irs
from pyshade.compiler.writer import TsxWriter, js_string


def emit_app(pages: list[PageIR], *, keep_alive: bool = False, color_scheme: str = 'system') -> str:
    """生成 app.gen.tsx:ShadeAppProvider(共享 store)+ ShadeRouter(页面表)。

    生成的 App 恒开深链(pageNames + deepLink);runtime 侧默认关闭是给
    testkit/手工挂载留的不串扰余地。keep_alive 经 Router 的 keepAlive prop 落地;
    color_scheme 恒发(localStorage 显式选择在 runtime 侧优先)。
    """
    if not pages:
        raise ValueError("emit_app 至少需要一个页面")

    bound_all: list[str] = []
    push_any = False
    for page in pages:
        bound, uses_push = page_binding_summary(page)
        bound_all.extend(bound)
        push_any = push_any or uses_push

    w = TsxWriter()
    w.line('/* 由 pyshade 编译器生成 — 请勿手改。 */')
    w.line('import { ShadeAppProvider, ShadeRouter } from "@/runtime/app";')
    for page in pages:
        w.line(f'import {{ {page.name} }} from "./pages/{page.name}.gen";')
    w.line()
    w.line('const PAGES = {')
    w.indent()
    for page in pages:
        w.line(f'{page.name},')
    w.dedent()
    w.line('};')
    if bound_all:
        w.line()
        w.line('const BOUND_PROPS = [')
        w.indent()
        for item in bound_all:
            w.line(f'{js_string(item)},')
        w.dedent()
        w.line('];')
    w.line()
    w.line('export default function App() {')
    w.indent()
    w.line('return (')
    w.indent()
    attrs = [f'initial={js_string(pages[0].name)}']
    if bound_all:
        attrs.append('boundProps={BOUND_PROPS}')
    if push_any:
        attrs.append('push')
    attrs.append('pageNames={Object.keys(PAGES)}')
    attrs.append('deepLink')
    attrs.append(f'colorScheme={js_string(color_scheme)}')
    router_attrs = ' keepAlive' if keep_alive else ''
    w.line(f'<ShadeAppProvider {" ".join(attrs)}>')
    w.indent()
    w.line(f'<ShadeRouter pages={{PAGES}}{router_attrs} />')
    w.dedent()
    w.line('</ShadeAppProvider>')
    w.dedent()
    w.line(');')
    w.dedent()
    w.line('}')
    return w.to_string()


def emit_manifest(pages: list[PageIR], *, extra_components: list[str] | None = None) -> str:
    """生成 manifest.json:handlerId 与组件集合清单(调试/测试/按需打包断言用)。"""

    def _collect_handler_ids(page: PageIR) -> list[str]:
        ids: list[str] = []

        def visit(node: NodeIR) -> None:
            for event in node.events:
                ids.append(event.handler_id)
            for child in node.children:
                visit(child)

        for root in page.roots:
            visit(root)
        return ids

    def _collect_tags(page: PageIR) -> list[str]:
        return sorted({node.tag for node in iter_node_irs(page)})

    data: dict[str, object] = {
        'pages': {page.name: _collect_handler_ids(page) for page in pages},
        'components': {page.name: _collect_tags(page) for page in pages},
    }
    if pages:
        data['routes'] = {'initial': pages[0].name, 'pages': [page.name for page in pages]}
    if extra_components:
        data['extra_components'] = sorted(extra_components)
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'
