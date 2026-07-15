"""页面定义:BoardPage(Each 列表)⇄ StatsPage(统计),双向导航。

- 客户端导航:navigate(Page 类) / navigate('页面名')(前向引用姿势),零 IPC;
- 服务端导航:handler 返回 Navigate(...),编码为 $nav patch;
- 页面状态 unmount 即丢,跨页存活的是 ServerState(切页后列表/统计不蒸发)。
"""

from typing import Any

from pyshade.components import Button, ButtonVariant, Card, Each, Input, Text
from pyshade.expr import ClientVal
from pyshade.nav import navigate
from pyshade.page import Page
from task_board import handlers
from task_board.state import BoardState


class StatsPage(Page):
    summary = Text(text=BoardState.summary)
    back = Button('返回看板', on_click=navigate('BoardPage'))
    clear_done = Button('清理已完成并返回', variant=ButtonVariant.DESTRUCTIVE, on_click=handlers.on_clear_done)

    card = Card(summary, back, clear_done, title='统计', description='服务端 Navigate 演示')


def _task_template(t: Any) -> Card:
    return Card(
        Text(t.title),
        Text('已完成', muted=True, visible=t.done),
        Button('切换状态', on_click=handlers.on_toggle),
    )


class BoardPage(Page):
    new_task = ClientVal('')

    task_input = Input(label='新任务', placeholder='要做点什么?', value=new_task)
    add = Button('添加', submit=True, on_click=handlers.on_add)
    tasks = Each(BoardState.tasks, render=_task_template, key='id')
    summary = Text(text=BoardState.summary, muted=True)
    goto_stats = Button('查看统计', variant=ButtonVariant.OUTLINE, on_click=navigate(StatsPage))

    card = Card(task_input, add, tasks, summary, goto_stats, title='任务看板', description='M2 路由 + Each 演示')
