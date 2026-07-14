"""实现 pyshade.asgi._types Protocol 的 fake,记录 resolve/reject/send 调用。"""

from typing import Any

from pyshade.asgi._types import ResolverLike
from pyshade.asgi._wire import H_CHANNEL, H_METHOD, H_PATH, H_QUERY


class FakeResolver:
    def __init__(self, arguments: dict[str, Any]) -> None:
        self._arguments = arguments
        self.resolved: list[str | bytes] = []
        self.rejected: list[str] = []

    @property
    def arguments(self) -> dict[str, Any]:
        return self._arguments

    def resolve(self, value: str | bytes) -> None:
        self.resolved.append(value)

    def reject(self, value: str) -> None:
        self.rejected.append(value)


class FakeInvoke:
    def __init__(self, command: str, resolver: FakeResolver) -> None:
        self._command = command
        self.resolver = resolver
        self.bound_parameters: Any = None
        self.rejected: list[str] = []

    @property
    def command(self) -> str:
        return self._command

    def bind_to(self, parameters: Any) -> ResolverLike | None:
        self.bound_parameters = parameters
        return self.resolver

    def reject(self, value: str) -> None:
        self.rejected.append(value)


class FakeChannel:
    def __init__(self) -> None:
        self.sent: list[str | bytes] = []

    def send(self, data: str | bytes) -> None:
        self.sent.append(data)


def make_invoke(
    method: str,
    path: str,
    *,
    body: bytes = b'',
    channel: str | None = '__CHANNEL__:1',
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> FakeInvoke:
    """构造一次 ASGI over IPC 请求的 FakeInvoke(测试 helper,参数上限规范豁免)。"""
    headers: list[tuple[bytes, bytes]] = [
        (H_METHOD, method.encode('ascii')),
        (H_PATH, path.encode('ascii')),
    ]
    if '?' in path:
        raise ValueError("pass query via extra_headers with H_QUERY")
    if channel is not None:
        headers.append((H_CHANNEL, channel.encode('ascii')))
    if extra_headers:
        headers.extend(extra_headers)
    resolver = FakeResolver({'body': body, 'headers': headers, 'webview_window': None})
    return FakeInvoke('__pyshade_asgi__', resolver)


__all__ = ['FakeChannel', 'FakeInvoke', 'FakeResolver', 'make_invoke', 'H_QUERY']
