"""app.gen.tsx + manifest.json 发射(设计 §3.4)。"""

import json

from pyshade.compiler.ir import PageIR
from pyshade.compiler.writer import TsxWriter


def emit_app(pages: list[PageIR]) -> str:
    """生成 app.gen.tsx:挂载首页;M0 单页。"""
    w = TsxWriter()
    w.line('/* 由 pyshade 编译器生成 — 请勿手改。 */')
    for page in pages:
        w.line(f'import {{ {page.name} }} from "./pages/{page.name}.gen";')
    w.line()
    w.line('export default function App() {')
    w.indent()
    w.line('return (')
    w.indent()
    if pages:
        w.line(f'<{pages[0].name} />')
    w.dedent()
    w.line(');')
    w.dedent()
    w.line('}')
    return w.to_string()


def emit_manifest(pages: list[PageIR]) -> str:
    """生成 manifest.json:handlerId 清单(调试/测试用)。"""

    def _collect_handler_ids(page: PageIR) -> list[str]:
        ids: list[str] = []

        def visit(node: object) -> None:
            from pyshade.compiler.ir import NodeIR

            if not isinstance(node, NodeIR):
                return
            for event in node.events:
                ids.append(event.handler_id)
            for child in node.children:
                visit(child)

        for root in page.roots:
            visit(root)
        return ids

    data: dict[str, object] = {
        'pages': {page.name: _collect_handler_ids(page) for page in pages},
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'
