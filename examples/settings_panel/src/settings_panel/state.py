"""服务端状态:字段赋值自动 diff(事件内随响应下发,请求外经 SSE 推送)。"""

from pyshade.state import ServerState


class PanelState(ServerState):
    status: str = '就绪'
    progress: str = ''
    save_count: int = 0


panel = PanelState()
