"""M2 Wave 2 组件编译:FormControlsPage golden(选项 prop + 数值受控 + 四形态交叉)。"""

import pytest

from pyshade.compiler.checks import CompileError, check_page_ir
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.ir import build_page_ir
from pyshade.components import Badge, Button, Card, Option, Progress, RadioGroup, Select, Slider, Text
from pyshade.events import EventContext
from pyshade.expr import ClientVal, value_of
from pyshade.page import Page
from pyshade.state import ServerState
from tests.compiler.test_compiler import golden_compare


def on_effort_change(ctx: EventContext) -> None: ...


def on_volume_change(ctx: EventContext) -> None: ...


def on_save(ctx: EventContext) -> None: ...


class FormState(ServerState):
    sync_pct: int = 0


class FormControlsPage(Page):
    """四形态交叉:Slider 值驱动 Badge、Select 值驱动 Text、ServerRef 驱动 Progress。"""

    theme = ClientVal('system')

    effort = Select(
        label='思考力度',
        placeholder='选择档位',
        options=['low', 'medium', 'high'],
        on_change=on_effort_change,
    )
    theme_radio = RadioGroup(
        label='主题',
        options=[Option(value='system', label='跟随系统'), Option(value='light', label='亮色')],
        value=theme,
    )
    volume = Slider(label='音量', value=30, max=200, step=5, on_change=on_volume_change)
    loud = Badge('响亮', visible=value_of(volume) > 100)
    effort_echo = Text(text='档位:' + value_of(effort), visible=value_of(effort) != '', muted=True)
    sync = Progress(FormState.sync_pct)
    save = Button('保存', submit=True, on_click=on_save)

    card = Card(effort, theme_radio, volume, loud, effort_echo, sync, save, title='表单控件', description='M2 Wave 2')


class TestFormControlsGolden:
    def test_form_controls_tsx(self) -> None:
        ir = build_page_ir(FormControlsPage)
        check_page_ir(ir)
        tsx = emit_page(ir)
        # 数值受控:useState<number> + 拖动本地 / 松手跨界
        assert 'const [volumeValue, setVolumeValue] = useState<number>(30);' in tsx
        assert 'onValueChange={([v]) => setVolumeValue(v)}' in tsx
        assert 'onValueCommit={([v]) => rt.fire("FormControlsPage.volume.on_change", { value: v })}' in tsx
        # 选项列表经 rt.ov(服务端可整表替换)后 map
        assert 'rt.ov<{ value: string; label: string }[]>("FormControlsPage.effort", "options"' in tsx
        assert '<SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>' in tsx
        # str 简写归一化 + Option 显式声明共存
        assert '{"value": "low", "label": "low"}' in tsx
        assert '{"value": "system", "label": "跟随系统"}' in tsx
        # 数值表达式驱动显隐
        assert '{(volumeValue > 100) && (' in tsx
        # collectValues 数值 union
        assert 'Record<string, string | boolean | number>' in tsx
        golden_compare('FormControlsPage.gen.tsx', tsx)


class TestWave2Checks:
    def test_empty_options_rejected(self) -> None:
        with pytest.raises(CompileError, match='选项列表为空'):

            class EmptyOptionsPage(Page):
                pick = Select(options=[])

            check_page_ir(build_page_ir(EmptyOptionsPage))

    def test_duplicate_option_value_rejected(self) -> None:
        class DupPage(Page):
            pick = Select(options=['a', 'a'])

        with pytest.raises(CompileError, match='重复'):
            check_page_ir(build_page_ir(DupPage))

    def test_empty_option_value_rejected(self) -> None:
        class EmptyValuePage(Page):
            pick = Select(options=[Option(value='', label='空')])

        with pytest.raises(CompileError, match='空串'):
            check_page_ir(build_page_ir(EmptyValuePage))

    def test_default_not_in_options_rejected(self) -> None:
        class BadDefaultPage(Page):
            pick = Select(options=['a', 'b'], value='c')

        with pytest.raises(CompileError, match='不在选项中'):
            check_page_ir(build_page_ir(BadDefaultPage))

    def test_slider_invalid_range_rejected(self) -> None:
        class BadRangePage(Page):
            bar = Slider(min=10, max=5)

        with pytest.raises(CompileError, match='区间非法'):
            check_page_ir(build_page_ir(BadRangePage))

    def test_slider_non_positive_step_rejected(self) -> None:
        class BadStepPage(Page):
            bar = Slider(step=0)

        with pytest.raises(CompileError, match='step'):
            check_page_ir(build_page_ir(BadStepPage))

    def test_slider_default_out_of_range_rejected(self) -> None:
        class OutOfRangePage(Page):
            bar = Slider(value=500)

        with pytest.raises(CompileError, match='不在区间'):
            check_page_ir(build_page_ir(OutOfRangePage))

    def test_client_val_bound_select_default_checked(self) -> None:
        class BadBindPage(Page):
            pick_val = ClientVal('nope')
            pick = Select(options=['a', 'b'], value=pick_val)

        with pytest.raises(CompileError, match='不在选项中'):
            check_page_ir(build_page_ir(BadBindPage))
