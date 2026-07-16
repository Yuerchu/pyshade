"""tag → live demo 工厂:每次调用全新实例(组件单父规则),工厂源码即演示代码。

- 返回值是页面命名空间片段(field 名 → Component/ClientVal),逐组件页原样并入;
- 服务端 demo 一律走 ServerState auto-diff(见 handlers.py),demo-mock.js 按 handlerId 复刻;
- 客户端 demo(受控/Expr/浮层)静态站上原生可交互,零模拟。
"""

from collections.abc import Callable
from typing import Any

from docs_site import handlers
from docs_site.state import DocsDemoState
from pyshade.components import (
    Accordion,
    AccordionItem,
    Alert,
    AlertDialog,
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
    PasswordInput,
    Progress,
    RadioGroup,
    ScrollArea,
    Select,
    Separator,
    Skeleton,
    Slider,
    Stack,
    Switch,
    TabItem,
    Tabs,
    Text,
    Textarea,
    Tooltip,
)
from pyshade.expr import ClientVal

DemoFactory = Callable[[], dict[str, Any]]


def demo_text() -> dict[str, Any]:
    return {
        'demo_plain': Text('A plain text line (server-patchable).'),
        'demo_muted': Text('A muted secondary line.', muted=True),
    }


def demo_heading() -> dict[str, Any]:
    return {
        'demo_h2': Heading('Section heading'),
        'demo_h4': Heading('Sub heading', level=4),
    }


def demo_link() -> dict[str, Any]:
    return {'demo_link': Link('PyShade on GitHub', 'https://github.com/Yuerchu/pyshade')}


def demo_markdown() -> dict[str, Any]:
    return {
        'demo_md': Markdown(
            '**Bold**, `inline code`, and a list:\n\n- rendered at compile time\n- raw HTML is always escaped'
        ),
    }


def demo_code_block() -> dict[str, Any]:
    return {'demo_code': CodeBlock("print('hello pyshade')\n", language='python')}


def demo_stack() -> dict[str, Any]:
    return {'demo_stack': Stack(Text('Stacked line one.'), Text('Stacked line two.', muted=True), width='sm')}


def demo_badge() -> dict[str, Any]:
    return {'demo_badge': Badge('New', variant=BadgeVariant.SECONDARY)}


def demo_alert() -> dict[str, Any]:
    return {'demo_alert': Alert('Heads up', description='Alerts carry a title and a description.')}


def demo_separator() -> dict[str, Any]:
    return {
        'demo_above': Text('Above the line.'),
        'demo_sep': Separator(),
        'demo_below': Text('Below the line.'),
    }


def demo_skeleton() -> dict[str, Any]:
    return {'demo_skeleton': Skeleton(width='12rem', height='1.25rem')}


def demo_progress() -> dict[str, Any]:
    return {'demo_progress': Progress(DocsDemoState.progress)}


def demo_button() -> dict[str, Any]:
    return {
        'demo_btn': Button('Click me', on_click=handlers.on_demo_click),
        'demo_btn_note': Text(DocsDemoState.click_note, muted=True),
    }


def demo_input() -> dict[str, Any]:
    name = ClientVal('')
    return {
        'demo_name': name,
        'demo_input': Input(label='Name', placeholder='Type here…', value=name),
        'demo_input_echo': Text('Hello, ' + name, visible=name != '', muted=True),
    }


def demo_password_input() -> dict[str, Any]:
    return {
        'demo_pw': PasswordInput(label='Password', placeholder='Sent only with submit'),
        'demo_pw_submit': Button('Submit', submit=True, on_click=handlers.on_submit_demo),
        'demo_pw_note': Text(DocsDemoState.submitted, muted=True),
    }


def demo_textarea() -> dict[str, Any]:
    return {'demo_ta': Textarea(label='Bio', placeholder='Multi-line input…', rows=3)}


def demo_checkbox() -> dict[str, Any]:
    agreed = ClientVal(False)
    return {
        'demo_agreed': agreed,
        'demo_cb': Checkbox(label='Accept the terms', checked=agreed),
        'demo_cb_note': Text('Accepted — thanks!', visible=agreed, muted=True),
    }


def demo_switch() -> dict[str, Any]:
    return {'demo_switch': Switch(label='Notifications')}


def demo_select() -> dict[str, Any]:
    return {'demo_select': Select(label='Effort', placeholder='Pick one', options=['low', 'medium', 'high'])}


def demo_radio_group() -> dict[str, Any]:
    return {
        'demo_radio': RadioGroup(
            label='Channel',
            options=[Option(value='stable', label='Stable'), Option(value='beta', label='Beta')],
        ),
    }


def demo_slider() -> dict[str, Any]:
    return {'demo_slider': Slider(label='Volume', value=30)}


def demo_card() -> dict[str, Any]:
    return {'demo_card': Card(Text('Card body content.'), title='Card title', description='Card description')}


def demo_dialog() -> dict[str, Any]:
    return {
        'demo_dialog': Dialog(
            Text('Dialog body.'),
            trigger=Button('Open dialog'),
            title='Hello',
            description='A trigger-slot dialog.',
        ),
    }


def demo_alert_dialog() -> dict[str, Any]:
    return {
        'demo_confirm': AlertDialog(
            'Proceed?',
            trigger=Button('Delete…', variant=ButtonVariant.DESTRUCTIVE),
            description='This demo only flips a ServerState field.',
            destructive=True,
            on_confirm=handlers.on_confirm_demo,
        ),
        'demo_confirm_note': Text(DocsDemoState.confirmed, muted=True),
    }


def demo_tooltip() -> dict[str, Any]:
    return {'demo_tooltip': Tooltip(Button('Hover me', variant=ButtonVariant.GHOST), text='Tooltip content')}


def demo_tabs() -> dict[str, Any]:
    return {
        'demo_tabs': Tabs(
            TabItem('One', Text('First tab content.')),
            TabItem('Two', Text('Second tab content.'), value='two'),
        ),
    }


def demo_accordion() -> dict[str, Any]:
    return {
        'demo_accordion': Accordion(
            AccordionItem('What is PyShade?', Text('A pure-Python desktop framework.')),
            AccordionItem('Zero Node?', Text('Yes — pip install is enough.'), value='node'),
        ),
    }


def demo_scroll_area() -> dict[str, Any]:
    return {
        'demo_scroll': ScrollArea(
            Text('Log line 1'),
            Text('Log line 2'),
            Text('Log line 3'),
            Text('Log line 4'),
            height='6rem',
        ),
    }


def _todo_row(item: Any) -> Card:
    return Card(Text(item.title))


def demo_each() -> dict[str, Any]:
    return {
        'demo_todos': Each(DocsDemoState.todos, render=_todo_row, key='id'),
        'demo_todo_add': Button('Add a task', on_click=handlers.on_todo_add),
    }


DEMOS: dict[str, DemoFactory] = {
    'Accordion': demo_accordion,
    'AccordionItem': demo_accordion,  # 子槽件与父容器共用演示
    'Alert': demo_alert,
    'AlertDialog': demo_alert_dialog,
    'Badge': demo_badge,
    'Button': demo_button,
    'Card': demo_card,
    'Checkbox': demo_checkbox,
    'CodeBlock': demo_code_block,
    'Dialog': demo_dialog,
    'Each': demo_each,
    'Heading': demo_heading,
    'Input': demo_input,
    'Link': demo_link,
    'Markdown': demo_markdown,
    'PasswordInput': demo_password_input,
    'Progress': demo_progress,
    'RadioGroup': demo_radio_group,
    'ScrollArea': demo_scroll_area,
    'Select': demo_select,
    'Separator': demo_separator,
    'Skeleton': demo_skeleton,
    'Slider': demo_slider,
    'Stack': demo_stack,
    'Switch': demo_switch,
    'TabItem': demo_tabs,  # 子槽件与父容器共用演示
    'Tabs': demo_tabs,
    'Text': demo_text,
    'Textarea': demo_textarea,
    'Tooltip': demo_tooltip,
}
