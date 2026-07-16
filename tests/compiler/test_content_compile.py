"""M4 Phase 1 内容组件编译:const binding 分类、Heading 档位发射、Link 字面量内联。"""

from pyshade.compiler.checks import check_page_ir
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.ir import build_page_ir, iter_node_irs
from pyshade.components import Card, Heading, Link, Switch, Text
from pyshade.expr import ClientVal
from pyshade.page import Page
from tests.compiler.test_compiler import golden_compare


class ContentPage(Page):
    detailed = ClientVal(False)

    title = Heading('内容组件', level=1)
    section = Heading('小节')
    fine = Heading('细则', level=4, visible=detailed)
    toggle = Switch(label='展开细则', checked=detailed)
    home = Link('项目主页', 'https://example.com/pyshade')
    mail = Link('联系我们', 'mailto:hi@example.com')
    note = Text('Heading/Link 演示', muted=True)

    card = Card(title, section, fine, toggle, home, mail, note, title='内容')


class TestContentGolden:
    def test_content_page_tsx(self) -> None:
        ir = build_page_ir(ContentPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # Heading 档位 → 标签与排版 class 构建期定档
        assert '<h1 className="scroll-m-20 text-4xl font-extrabold tracking-tight">' in tsx
        assert '<h2 className="scroll-m-20 text-3xl font-semibold tracking-tight">' in tsx
        assert '<h4 className="scroll-m-20 text-xl font-semibold tracking-tight">' in tsx
        # Heading.text 仍是 plain(rt.ov 可 patch);level 不发射 rt.ov
        assert 'rt.ov("ContentPage.title", "text", "内容组件")' in tsx
        assert '"level"' not in tsx
        # Link const:字面量内联,无 rt.ov
        assert 'href={"https://example.com/pyshade"}' in tsx
        assert 'href={"mailto:hi@example.com"}' in tsx
        assert 'target="_blank" rel="noreferrer"' in tsx
        assert 'rt.ov("ContentPage.home", "href"' not in tsx
        assert 'rt.ov("ContentPage.home", "text"' not in tsx
        golden_compare('ContentPage.gen.tsx', tsx)


class TestConstBinding:
    def test_ir_classifies_const(self) -> None:
        ir = build_page_ir(ContentPage)
        by_anchor = {node.anchor: node for node in iter_node_irs(ir)}

        link_bindings = {p.name: p.binding for p in by_anchor['ContentPage.home'].props}
        assert link_bindings['text'] == 'const'
        assert link_bindings['href'] == 'const'
        assert link_bindings['visible'] == 'plain'

        heading_bindings = {p.name: p.binding for p in by_anchor['ContentPage.title'].props}
        assert heading_bindings['level'] == 'const'
        assert heading_bindings['text'] == 'plain'

    def test_const_not_in_bound_props(self) -> None:
        # const 不是客户端所有(expr/client_bind),不应进 boundProps 防御名单
        from pyshade.compiler.emit_page import page_binding_summary

        bound_props, _uses_push = page_binding_summary(build_page_ir(ContentPage))
        assert not any('.href' in p or '.level' in p for p in bound_props)
