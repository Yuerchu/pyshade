"""ASGI 类型别名与 pytauri 侧的 Protocol 抽象(design.md §3.7)。

`_wire`/`_bridge` 只依赖本模块的 Protocol,运行时不 import pytauri——
测试注入 fake 即可覆盖核心管线;pytauri 升级破坏结构时由契约测试报警。
"""

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, Protocol, TypeAlias

Scope: TypeAlias = MutableMapping[str, Any]
Message: TypeAlias = MutableMapping[str, Any]
Receive: TypeAlias = Callable[[], Awaitable[Message]]
Send: TypeAlias = Callable[[Message], Awaitable[None]]
ASGIApp: TypeAlias = Callable[[Scope, Receive, Send], Awaitable[None]]

InvokeHandler: TypeAlias = Callable[[Any], Any]
"""结构等价于 pytauri 的 _InvokeHandlerProto:def handler(invoke, /) -> Any。"""


class ResolverLike(Protocol):
    """pytauri InvokeResolver 的结构子集。"""

    @property
    def arguments(self) -> dict[str, Any]: ...

    def resolve(self, value: str | bytes, /) -> None: ...

    def reject(self, value: str, /) -> None: ...


class InvokeLike(Protocol):
    """pytauri Invoke 的结构子集。"""

    @property
    def command(self) -> str: ...

    def bind_to(self, parameters: Any, /) -> ResolverLike | None: ...

    def reject(self, value: str, /) -> None: ...


class ChannelLike(Protocol):
    """pytauri Channel 的结构子集(流式帧的出口);send 为 positional-only 对齐 pytauri。"""

    def send(self, data: str | bytes, /) -> None: ...


ChannelFactory: TypeAlias = Callable[[str, Any], ChannelLike]
"""(channel_id, webview_window) -> ChannelLike;真实实现在 _adapter,测试注入 fake。"""
