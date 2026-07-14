"""页面定义:SettingsPanelPage —— 一个 prop 的四种绑定形态同页演示。

- 普通值:服务端所有,Update 可 patch(M0 语义)
- Expr / ClientVal:客户端所有,编译为内联 JS + 共用 useState,交互期间零 IPC
- ServerRef:ServerState 字段所有,auto-diff / SSE 推送自动到达
"""

from pyshade.components import Button, ButtonVariant, Card, Input, Switch, Text
from pyshade.expr import ClientVal, value_of
from pyshade.page import Page
from settings_panel import handlers
from settings_panel.state import PanelState


class SettingsPanelPage(Page):
    # ClientState:纯前端联动(开关 → 禁用/显隐/拼接),打开 DevTools 看不到任何 IPC
    thinking = ClientVal(True)
    dark = ClientVal(False)
    nick = ClientVal('')

    thinking_switch = Switch(label='思考模式', checked=thinking)
    dark_switch = Switch(label='深色模式', checked=dark)
    effort = Input(label='思考力度', placeholder='low / medium / high', disabled=~thinking)
    nickname = Input(label='昵称', value=nick)
    greeting = Text(text='你好,' + nick + '!', visible=nick != '', muted=True)
    echo = Text(text='思考力度:' + value_of(effort), visible=value_of(effort) != '', muted=True)
    both = Text('思考与深色已同时开启', visible=thinking & dark, muted=True)

    # ServerState:handler 里给字段赋值即可,不写 Update;后台任务变更经 SSE 推送
    status = Text(text=PanelState.status)
    progress = Text(text=PanelState.progress, muted=True)

    save = Button('保存设置', submit=True, on_click=handlers.on_save)
    run_job = Button('运行后台任务(SSE 推送)', variant=ButtonVariant.OUTLINE, on_click=handlers.on_run_job)

    card = Card(
        thinking_switch,
        dark_switch,
        effort,
        nickname,
        greeting,
        echo,
        both,
        status,
        progress,
        save,
        run_job,
        title='设置面板',
        description='PyShade M1 演示:表达式 + ServerState + 推送',
    )
