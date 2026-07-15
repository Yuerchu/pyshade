"""M2 Wave 1 组件编译:GalleryPage golden(7 复刻组件 + 数值放宽 + 表达式联动)。"""

import pytest

from pyshade.compiler.checks import CompileError, check_page_ir
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.ir import build_page_ir
from pyshade.components import (
    Alert,
    AlertVariant,
    Badge,
    BadgeVariant,
    Card,
    Checkbox,
    Orientation,
    Progress,
    Separator,
    Skeleton,
    Text,
    Textarea,
)
from pyshade.events import EventContext
from pyshade.expr import ClientVal, value_of
from pyshade.page import Page
from pyshade.state import ServerState
from tests.compiler.test_compiler import golden_compare


def on_note_change(ctx: EventContext) -> None: ...


def on_agree_change(ctx: EventContext) -> None: ...


class GalleryState(ServerState):
    upload_pct: int = 0
    notice: str = ''


class GalleryPage(Page):
    """Wave 1 全组件:纯展示 + 受控复刻 + 数值 ServerRef + Checkbox 驱动的表达式联动。"""

    agree = ClientVal(False)

    heading = Text('组件画廊')
    tag = Badge('新功能', variant=BadgeVariant.SECONDARY)
    warn = Alert('注意', description='这是一条演示提示', variant=AlertVariant.DESTRUCTIVE)
    divider = Separator(orientation=Orientation.HORIZONTAL)
    loading = Skeleton(width='8rem', height='1.25rem')
    upload = Progress(GalleryState.upload_pct)
    note = Textarea(label='备注', placeholder='写点什么…', rows=4, on_change=on_note_change)
    agree_box = Checkbox(label='同意条款', checked=agree, on_change=on_agree_change)
    agreed_badge = Badge('已同意', visible=agree)
    note_echo = Text(text='备注:' + value_of(note), visible=value_of(note) != '', muted=True)

    card = Card(
        heading,
        tag,
        warn,
        divider,
        loading,
        upload,
        note,
        agree_box,
        agreed_badge,
        note_echo,
        title='画廊',
        description='M2 Wave 1',
    )


class TestGalleryGolden:
    def test_gallery_page_tsx(self) -> None:
        ir = build_page_ir(GalleryPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # 受控泛化:Checkbox(bool)与 Textarea(str)各自推导 useState 类型
        assert 'const [agreeValue, setAgreeValue] = useState<boolean>(false);' in tsx
        assert 'const [noteValue, setNoteValue] = useState<string>("");' in tsx
        # Checkbox 三态归一化
        assert 'setAgreeValue(checked === true)' in tsx
        # 数值 ServerRef 进 Progress
        assert '<Progress value={rt.ov("$s:GalleryState", "upload_pct", 0)} />' in tsx
        # 表达式联动
        assert '{(agreeValue) && (' in tsx or '{agreeValue && (' in tsx
        golden_compare('GalleryPage.gen.tsx', tsx)


class TestWave1Checks:
    def test_progress_literal_out_of_range(self) -> None:
        class BadProgressPage(Page):
            bar = Progress(120)

        with pytest.raises(CompileError, match='越界'):
            check_page_ir(build_page_ir(BadProgressPage))

    def test_numeric_category_interop(self) -> None:
        # INT 字段绑到 int|float prop:数值放宽后应通过
        class NumericOkPage(Page):
            bar = Progress(GalleryState.upload_pct)

        check_page_ir(build_page_ir(NumericOkPage))

    def test_str_ref_on_numeric_prop_rejected(self) -> None:
        class BadTypePage(Page):
            bar = Progress(GalleryState.notice)  # pyright: ignore[reportArgumentType]

        with pytest.raises(CompileError, match='不匹配'):
            check_page_ir(build_page_ir(BadTypePage))
