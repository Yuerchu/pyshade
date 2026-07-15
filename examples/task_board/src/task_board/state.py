"""ServerState:任务列表(Each 的数据源)与统计摘要。"""

from pydantic import BaseModel

from pyshade.state import ServerState


class TaskItem(BaseModel):
    """Each 项模型:扁平标量字段(M2 约束)。"""

    id: int
    title: str
    done: bool = False


class BoardState(ServerState):
    tasks: list[TaskItem] = [
        TaskItem(id=1, title='写周报'),
        TaskItem(id=2, title='评审同事的 PR', done=True),
        TaskItem(id=3, title='准备演示材料'),
    ]
    summary: str = '共 3 项,已完成 1 项'


board = BoardState()


def refresh_summary() -> None:
    done = sum(1 for t in board.tasks if t.done)
    board.summary = f"共 {len(board.tasks)} 项,已完成 {done} 项"
