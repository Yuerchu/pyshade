"""demo 的真实 Python handler(pyshade dev / 原生窗口模式使用)。

静态站上这些 handler 由 assets/demo-mock.js 按 handlerId 在客户端模拟
(用户已接受的双份维护,design.md §3.10);键集合对账测试防"缺口"漂移。
"""

from docs_site.state import TodoItem, docs_state
from pyshade.events import EventContext


def on_demo_click(ctx: EventContext) -> None:
    docs_state.clicks = docs_state.clicks + 1
    docs_state.click_note = f'clicked {docs_state.clicks} time(s)'


def on_todo_add(ctx: EventContext) -> None:
    next_id = max((item.id for item in docs_state.todos), default=0) + 1
    docs_state.todos = [*docs_state.todos, TodoItem(id=next_id, title=f'Task #{next_id}')]


def on_confirm_demo(ctx: EventContext) -> None:
    docs_state.confirmed = 'confirmed!'


def on_submit_demo(ctx: EventContext) -> None:
    docs_state.submitted = f'{len(ctx.values)} field(s) received'
