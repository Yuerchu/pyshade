"""组件画廊:26 个组件 + Each + 路由全铺开。

这个 example 的首要职责是给 CI 提供"真实 tsc"校验面——生成代码的每种发射形态
(受控 useState、选项 map、asChild 槽、多槽容器、.map 模板、rt.navigate、const 字面量、
编译期 markdown/高亮)都在这里出现一次。
"""

from typing import Any

from component_gallery import handlers
from component_gallery.state import GalleryDemoState
from pyshade.components import (
    Accordion,
    AccordionItem,
    Alert,
    AlertDialog,
    AlertVariant,
    Badge,
    BadgeVariant,
    Button,
    ButtonVariant,
    Card,
    Checkbox,
    CodeBlock,
    Dialog,
    Each,
    Heading,
    Input,
    Link,
    Markdown,
    Option,
    Orientation,
    PasswordInput,
    Progress,
    RadioGroup,
    ScrollArea,
    Select,
    Separator,
    Skeleton,
    Slider,
    Switch,
    TabItem,
    Tabs,
    Text,
    Textarea,
    Tooltip,
)
from pyshade.expr import ClientVal, value_of
from pyshade.nav import navigate
from pyshade.page import Page
from pyshade.scheme import toggle_color_scheme


class WidgetsPage(Page):
    """Wave 1 纯展示组件 + M4 内容组件 + ServerRef 进度。"""

    heading = Heading('组件画廊 — 展示件', level=1)
    intro = Text('每种发射形态在四个页面各出现一次')
    tag = Badge('M4', variant=BadgeVariant.SECONDARY)
    notice = Alert('提示', description='四个页面覆盖全部 26 个组件', variant=AlertVariant.DEFAULT)
    divider = Separator(orientation=Orientation.HORIZONTAL)
    placeholder = Skeleton(width='10rem', height='1.25rem')
    upload = Progress(GalleryDemoState.upload_pct)
    repo = Link('PyShade 源码', 'https://github.com/Yuerchu/pyshade')
    dark_toggle = Button('明暗切换', variant=ButtonVariant.GHOST, on_click=toggle_color_scheme())
    readme = Markdown(
        '**内容组件**支持表格、`行内代码`与任务列表:\n\n'
        '| 组件 | 渲染时机 |\n|---|---|\n| Markdown | 编译期 |\n| CodeBlock | 编译期 |\n\n'
        '- [x] escape=True 拒绝 raw HTML\n- [ ] 运行时 markdown(§6 开放)'
    )
    snippet = CodeBlock(
        'from pyshade.components import Markdown\n\ndoc = Markdown("**hello**")\n',
        language='python',
    )

    goto_form = Button('表单件', variant=ButtonVariant.OUTLINE, on_click=navigate('FormPage'))
    goto_overlays = Button('浮层件', variant=ButtonVariant.OUTLINE, on_click=navigate('OverlaysPage'))
    goto_structure = Button('结构件', variant=ButtonVariant.OUTLINE, on_click=navigate('StructurePage'))

    card = Card(
        heading,
        intro,
        tag,
        notice,
        divider,
        placeholder,
        upload,
        repo,
        dark_toggle,
        readme,
        snippet,
        goto_form,
        goto_overlays,
        goto_structure,
        title='展示件',
        description='Heading / Text / Badge / Alert / Separator / Skeleton / Progress / Link / Markdown / CodeBlock',
    )


class FormPage(Page):
    """受控输入全家桶:文本/敏感/多行/勾选/开关/选项/数值。"""

    dark = ClientVal(False)

    username = Input(label='用户名', placeholder='请输入用户名')
    password = PasswordInput(label='密码', placeholder='仅随 submit 跨界')
    bio = Textarea(label='简介', placeholder='写点什么…', rows=3)
    agree = Checkbox(label='同意条款')
    dark_switch = Switch(label='深色模式', checked=dark)
    effort = Select(label='思考力度', placeholder='选择档位', options=['low', 'medium', 'high'])
    theme = RadioGroup(
        label='主题', options=[Option(value='system', label='跟随系统'), Option(value='light', label='亮色')]
    )
    volume = Slider(label='音量', value=30)
    effort_echo = Text(text='档位:' + value_of(effort), visible=value_of(effort) != '', muted=True)

    save = Button('提交', submit=True, on_click=handlers.on_submit)
    back = Button('返回展示件', variant=ButtonVariant.GHOST, on_click=navigate('WidgetsPage'))

    card = Card(
        username,
        password,
        bio,
        agree,
        dark_switch,
        effort,
        theme,
        volume,
        effort_echo,
        save,
        back,
        title='表单件',
        description='Input / PasswordInput / Textarea / Checkbox / Switch / Select / RadioGroup / Slider',
    )


class OverlaysPage(Page):
    """浮层三件:trigger 槽 Dialog、受控 open Dialog、AlertDialog、Tooltip。"""

    settings_open = ClientVal(False)

    edit_dialog = Dialog(
        Input(label='昵称'),
        Text('修改后立即生效', muted=True),
        trigger=Button('编辑资料', variant=ButtonVariant.OUTLINE),
        title='编辑',
        description='trigger 槽形态',
    )
    settings_dialog = Dialog(Text('设置内容'), title='设置', open=settings_open)
    reset_confirm = AlertDialog(
        '确定重置进度吗?',
        trigger=Button('重置进度', variant=ButtonVariant.DESTRUCTIVE),
        description='此操作会把上传进度归零',
        confirm_text='重置',
        destructive=True,
        on_confirm=handlers.on_confirm_reset,
        on_cancel=handlers.on_cancel_reset,
    )
    hint = Tooltip(Button('悬停看提示', variant=ButtonVariant.GHOST), text='Tooltip 是 wrapper 容器')
    back = Button('返回展示件', variant=ButtonVariant.GHOST, on_click=navigate('WidgetsPage'))

    card = Card(
        edit_dialog,
        settings_dialog,
        reset_confirm,
        hint,
        back,
        title='浮层件',
        description='Dialog / AlertDialog / Tooltip',
    )


def _changelog_template(entry: Any) -> Card:
    return Card(Text(entry.version), Text(entry.note, muted=True))


class StructurePage(Page):
    """多槽容器 + Each 列表渲染。"""

    panels = Tabs(
        TabItem('账号', Card(Input(label='用户名'), title='账号信息')),
        TabItem('通知', Text('通知设置'), value='notify'),
    )
    faq = Accordion(
        AccordionItem('什么是 PyShade?', Text('纯 Python 桌面应用框架')),
        AccordionItem('需要 Node 吗?', Text('不需要,pip 装完即可打包'), value='node'),
        multiple=True,
    )
    logs = ScrollArea(Text('日志 1'), Text('日志 2'), height='8rem')
    changelog = Each(GalleryDemoState.changelog, render=_changelog_template)
    back = Button('返回展示件', variant=ButtonVariant.GHOST, on_click=navigate('WidgetsPage'))

    card = Card(
        panels,
        faq,
        logs,
        changelog,
        back,
        title='结构件',
        description='Tabs / Accordion / ScrollArea / Each',
    )
