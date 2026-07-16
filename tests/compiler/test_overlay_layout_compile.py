"""M2 Wave 3 组件编译:OverlayPage(浮层)与 LayoutPage(多槽嵌套)golden + 嵌套 G 规则。"""

import warnings

import pytest

from pyshade.compiler.checks import CompileError, check_page_ir
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.ir import build_page_ir
from pyshade.components import (
    Accordion,
    AccordionItem,
    AlertDialog,
    Button,
    ButtonVariant,
    Card,
    Dialog,
    Input,
    ScrollArea,
    TabItem,
    Tabs,
    Text,
    Tooltip,
    TooltipSide,
)
from pyshade.events import EventContext
from pyshade.expr import ClientVal
from pyshade.page import Page
from tests.compiler.test_compiler import golden_compare


def on_confirm_delete(ctx: EventContext) -> None: ...


def on_cancel_delete(ctx: EventContext) -> None: ...


class OverlayPage(Page):
    """浮层三件:trigger 槽 Dialog、受控 open Dialog、AlertDialog、Tooltip wrapper。"""

    settings_open = ClientVal(False)

    edit_dialog = Dialog(
        Input(label='昵称'),
        Text('修改后立即生效', muted=True),
        trigger=Button('编辑资料', variant=ButtonVariant.OUTLINE),
        title='编辑',
        description='更新你的公开资料',
    )
    settings_dialog = Dialog(
        Text('设置内容'),
        title='设置',
        open=settings_open,
    )
    open_settings = Button('打开设置', on_click=None)
    delete_confirm = AlertDialog(
        '确定删除吗?',
        trigger=Button('删除', variant=ButtonVariant.DESTRUCTIVE),
        description='此操作不可撤销',
        confirm_text='删除',
        destructive=True,
        on_confirm=on_confirm_delete,
        on_cancel=on_cancel_delete,
    )
    hint = Tooltip(Button('悬停看提示', variant=ButtonVariant.GHOST), text='这是提示', side=TooltipSide.RIGHT)

    card = Card(
        edit_dialog, settings_dialog, open_settings, delete_confirm, hint, title='浮层', description='M2 Wave 3'
    )


class LayoutPage(Page):
    """多槽嵌套:Tabs 套 Card 套 Input(三层)+ Accordion + ScrollArea。"""

    panels = Tabs(
        TabItem(
            '账号',
            Card(Input(label='用户名'), title='账号信息'),
        ),
        TabItem(
            '通知',
            Text('通知设置'),
            value='notify',
        ),
    )
    faq = Accordion(
        AccordionItem('什么是 PyShade?', Text('纯 Python 桌面应用框架')),
        AccordionItem('需要 Node 吗?', Text('不需要,pip 装完即可打包'), value='node'),
        multiple=True,
    )
    logs = ScrollArea(Text('日志 1'), Text('日志 2'), height='10rem')

    card = Card(panels, faq, logs, title='布局', description='M2 Wave 3')


class TestOverlayGolden:
    def test_overlay_page_tsx(self) -> None:
        ir = build_page_ir(OverlayPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # trigger 槽:asChild 包裹,且 trigger 子组件不发 visible guard
        assert '<DialogTrigger asChild>' in tsx
        assert '<AlertDialogTrigger asChild>' in tsx
        # 受控 open:ClientVal 共用 useState
        assert 'const [settings_openValue, setSettings_openValue] = useState<boolean>(false);' in tsx
        assert 'open={settings_openValue} onOpenChange={setSettings_openValue}' in tsx
        # AlertDialog 事件与 destructive 样式
        assert 'rt.fire("OverlayPage.delete_confirm.on_confirm", {})' in tsx
        assert 'rt.fire("OverlayPage.delete_confirm.on_cancel", {})' in tsx
        assert 'bg-destructive' in tsx
        # Tooltip wrapper
        assert '<TooltipTrigger asChild>' in tsx
        assert 'side={rt.ov("OverlayPage.hint", "side", "right")}' in tsx
        golden_compare('OverlayPage.gen.tsx', tsx)


class TestLayoutGolden:
    def test_layout_page_tsx(self) -> None:
        ir = build_page_ir(LayoutPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # 非受控 Tabs:defaultValue 取首 item(value 缺省 = label)
        assert '<Tabs defaultValue="账号">' in tsx
        assert '<TabsTrigger value="账号">' in tsx
        assert '<TabsContent value="notify"' in tsx
        # 三层嵌套:TabItem 内 Card 内 Input 的受控 useState 正常生成
        assert 'useState<string>("")' in tsx
        # Accordion multiple
        assert '<Accordion type="multiple">' in tsx
        assert '<AccordionTrigger>' in tsx
        # ScrollArea 高度
        assert '<ScrollArea style={{ height: "10rem" }}' in tsx
        golden_compare('LayoutPage.gen.tsx', tsx)


class TestWave3Checks:
    def test_tab_item_outside_tabs_rejected(self) -> None:
        class OrphanTabPage(Page):
            item = TabItem('孤儿', Text('内容'))

        with pytest.raises(CompileError, match='只能是 Tabs 的直接子组件'):
            check_page_ir(build_page_ir(OrphanTabPage))

    def test_tabs_with_non_tab_item_rejected(self) -> None:
        class BadTabsPage(Page):
            panels = Tabs(Text('裸内容'))  # 静态签名收 Component,嵌套合法性由 G 规则把关

        with pytest.raises(CompileError, match='必须全为 TabItem'):
            check_page_ir(build_page_ir(BadTabsPage))

    def test_duplicate_item_value_rejected(self) -> None:
        class DupValuePage(Page):
            panels = Tabs(TabItem('A'), TabItem('B', value='A'))

        with pytest.raises(CompileError, match='重复'):
            check_page_ir(build_page_ir(DupValuePage))

    def test_accordion_item_outside_accordion_rejected(self) -> None:
        class OrphanAccordionPage(Page):
            wrapper = Card(AccordionItem('孤儿', Text('内容')))

        with pytest.raises(CompileError, match='只能是 Accordion 的直接子组件'):
            check_page_ir(build_page_ir(OrphanAccordionPage))

    def test_dialog_trigger_with_on_click_rejected(self) -> None:
        def on_click(ctx: EventContext) -> None: ...

        class BadTriggerPage(Page):
            dlg = Dialog(Text('内容'), trigger=Button('打开', on_click=on_click), title='标题')

        with pytest.raises(CompileError, match='不得绑定 on_click'):
            check_page_ir(build_page_ir(BadTriggerPage))

    def test_dialog_trigger_visible_false_rejected(self) -> None:
        # trigger 进 no_guard_anchors 不发 guard,非默认 visible 会被静默忽略(同 Tooltip 宿主规则)
        class HiddenTriggerPage(Page):
            dlg = Dialog(Text('内容'), trigger=Button('打开', visible=False), title='标题')

        with pytest.raises(CompileError, match='visible 必须保持默认 True'):
            check_page_ir(build_page_ir(HiddenTriggerPage))

    def test_unreachable_dialog_warns(self) -> None:
        class DeadDialogPage(Page):
            dlg = Dialog(Text('内容'), title='标题')

        with pytest.warns(UserWarning, match='永远无法打开'):
            check_page_ir(build_page_ir(DeadDialogPage))

    def test_tooltip_child_with_expr_visible_rejected(self) -> None:
        class BadTooltipPage(Page):
            flag = ClientVal(True)
            probe = Button('占位')  # 让 flag 有绑定豁免告警不重要,直接 expr 引用
            tip = Tooltip(Button('宿主', visible=flag), text='提示')

        with pytest.raises(CompileError, match='asChild'):
            check_page_ir(build_page_ir(BadTooltipPage))

    def test_valid_pages_pass_without_warnings(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            check_page_ir(build_page_ir(LayoutPage))
