"""ASGI over IPC 适配层(design.md §3.7)。

自定义 pytauri `invoke_handler` 把原始 Invoke(command/headers/body)映射成 ASGI scope
喂给 FastAPI,`resolve(bytes)` 回填响应,流式经 Tauri Channel。全程无 TCP 端口。

对 pyshade 其余部分零耦合,是未来拆分独立包(pytauri-asgi)的天然切割线。
"""

from pyshade.asgi._adapter import AsgiIpcAdapter
from pyshade.asgi._lifespan import LifespanError, LifespanManager
from pyshade.asgi._types import (
    ASGIApp,
    ChannelFactory,
    ChannelLike,
    InvokeHandler,
    InvokeLike,
    ResolverLike,
)
from pyshade.asgi._wire import ASGI_COMMAND, WireError

__all__ = [
    'ASGI_COMMAND',
    'ASGIApp',
    'AsgiIpcAdapter',
    'ChannelFactory',
    'ChannelLike',
    'InvokeHandler',
    'InvokeLike',
    'LifespanError',
    'LifespanManager',
    'ResolverLike',
    'WireError',
]
