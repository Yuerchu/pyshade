"""文档站 demo 的 ServerState:服务端 demo 一律走 auto-diff(不用 Update)。

handler 因此无需引用组件实例——静态站的 demo-mock.js 只需按 handlerId 复刻
"改哪个字段、怎么改",与真实 Python 实现逐条对应(键集合有对账测试)。
"""

from pydantic import BaseModel

from pyshade.state import ServerState


class TodoItem(BaseModel):
    id: int
    title: str


class DocsDemoState(ServerState):
    clicks: int = 0
    click_note: str = 'not clicked yet'
    progress: int = 40
    confirmed: str = 'not yet'
    submitted: str = 'nothing yet'
    todos: list[TodoItem] = [
        TodoItem(id=1, title='Read the quickstart'),
        TodoItem(id=2, title='Build your first page'),
    ]


docs_state = DocsDemoState()
