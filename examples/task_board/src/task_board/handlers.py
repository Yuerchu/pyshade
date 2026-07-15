"""事件 handler:Each 模板事件(item_key 定位)+ 整表替换 + 服务端 Navigate。"""

from pyshade.events import EventContext
from pyshade.nav import Navigate
from task_board.state import TaskItem, board, refresh_summary


def on_toggle(ctx: EventContext) -> None:
    """模板共享 handler:ctx.item_key(= TaskItem.id)定位;整表替换驱动 auto-diff。"""
    board.tasks = [t.model_copy(update={'done': not t.done}) if t.id == ctx.item_key else t for t in board.tasks]
    refresh_summary()


def on_add(ctx: EventContext) -> None:
    title = str(ctx.values.get('new_task', '')).strip()
    if not title:
        return
    next_id = max((t.id for t in board.tasks), default=0) + 1
    # 惯用法:原地 append 不触发描述符赋值,必须整表替换
    board.tasks = [*board.tasks, TaskItem(id=next_id, title=title)]
    refresh_summary()


def on_clear_done(ctx: EventContext) -> list[Navigate]:
    """服务端导航:清理数据后跳回看板($nav patch 与 auto-diff 同一 envelope 到达)。"""
    board.tasks = [t for t in board.tasks if not t.done]
    refresh_summary()
    return [Navigate('BoardPage')]
