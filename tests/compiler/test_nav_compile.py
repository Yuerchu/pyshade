"""M2 Phase 5 路由编译:navigate 发射、app.gen.tsx 新形态、check_app 负例、manifest routes。"""

import json

import pytest

from pyshade.compiler.checks import CompileError, check_app, check_page_ir
from pyshade.compiler.emit_app import emit_app, emit_manifest
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.ir import PageIR, build_page_ir
from pyshade.components import Button, ButtonVariant, Card, Dialog, Switch, Text
from pyshade.expr import ClientVal
from pyshade.nav import navigate
from pyshade.page import Page
from pyshade.state import ServerState
from tests.compiler.test_compiler import golden_compare


class NavCompileState(ServerState):
    status: str = '就绪'


class NavDetailPage(Page):
    """字符串目标(互相导航的前向引用姿势)+ ServerRef(验证 App 级 push 聚合)。"""

    info = Text(NavCompileState.status)
    back = Button('返回', on_click=navigate('NavHomePage'))

    card = Card(info, back, title='详情')


class NavHomePage(Page):
    """类目标 + 表达式绑定(验证 App 级 boundProps 聚合)。"""

    dense = ClientVal(False)
    density = Switch(label='紧凑模式', checked=dense)
    hint = Text('紧凑模式已开启', visible=dense)
    goto = Button('查看详情', variant=ButtonVariant.OUTLINE, on_click=navigate(NavDetailPage))

    card = Card(density, hint, goto, title='主页')


def _page_irs() -> list[PageIR]:
    return [build_page_ir(NavHomePage), build_page_ir(NavDetailPage)]


class TestNavGolden:
    def test_home_page_tsx(self) -> None:
        ir = build_page_ir(NavHomePage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # navigate:零 IPC,不发 rt.fire
        assert 'onClick={() => rt.navigate("NavDetailPage")}' in tsx
        assert 'rt.fire' not in tsx
        golden_compare('NavHomePage.gen.tsx', tsx)

    def test_string_target_emits_identically(self) -> None:
        tsx = emit_page(build_page_ir(NavDetailPage))
        assert 'onClick={() => rt.navigate("NavHomePage")}' in tsx

    def test_app_two_pages(self) -> None:
        irs = _page_irs()
        check_app(irs)
        tsx = emit_app(irs)
        assert 'import { ShadeAppProvider, ShadeRouter } from "@/runtime/app";' in tsx
        assert 'initial="NavHomePage"' in tsx
        # boundProps 全页聚合;DetailPage 的 ServerRef 让 App 级 push 开启
        assert '"NavHomePage.density.checked",' in tsx
        assert '"NavHomePage.hint.visible",' in tsx
        assert 'boundProps={BOUND_PROPS} push pageNames={Object.keys(PAGES)} deepLink>' in tsx
        golden_compare('app_nav.gen.tsx', tsx)

    def test_deep_link_attrs_always_emitted(self) -> None:
        tsx = emit_app(_page_irs())
        assert 'pageNames={Object.keys(PAGES)} deepLink' in tsx
        assert 'keepAlive' not in tsx  # 默认不保活

    def test_keep_alive_router_prop(self) -> None:
        tsx = emit_app(_page_irs(), keep_alive=True)
        assert '<ShadeRouter pages={PAGES} keepAlive />' in tsx

    def test_shade_app_keep_alive_param(self) -> None:
        from pyshade.app import ShadeApp

        assert ShadeApp(pages=[NavHomePage]).keep_alive is False
        assert ShadeApp(pages=[NavHomePage], keep_alive=True).keep_alive is True

    def test_manifest_routes(self) -> None:
        data = json.loads(emit_manifest(_page_irs()))
        assert data['routes'] == {'initial': 'NavHomePage', 'pages': ['NavHomePage', 'NavDetailPage']}
        # navigate 不产生 handlerId
        assert data['pages']['NavHomePage'] == []
        assert data['pages']['NavDetailPage'] == []


class TestCheckApp:
    def test_navigate_target_missing(self) -> None:
        class LonelyPage(Page):
            goto = Button('去哪', on_click=navigate('NowherePage'))

        with pytest.raises(CompileError, match="navigate 目标 'NowherePage'"):
            check_app([build_page_ir(LonelyPage)])

    def test_duplicate_page_names(self) -> None:
        def make_page() -> type[Page]:
            class DupPage(Page):
                text = Text('x')

            return DupPage

        with pytest.raises(CompileError, match="页面类名 'DupPage' 重复"):
            check_app([build_page_ir(make_page()), build_page_ir(make_page())])

    def test_submit_navigate_conflict(self) -> None:
        class SubmitNavPage(Page):
            btn = Button('提交并跳转', submit=True, on_click=navigate('SubmitNavPage'))

        with pytest.raises(CompileError, match='submit=True'):
            check_page_ir(build_page_ir(SubmitNavPage))

    def test_dialog_trigger_navigate_rejected(self) -> None:
        class TriggerNavPage(Page):
            dlg = Dialog(Text('内容'), trigger=Button('打开', on_click=navigate('TriggerNavPage')), title='T')

        with pytest.raises(CompileError, match='不得绑定 on_click'):
            check_page_ir(build_page_ir(TriggerNavPage))
