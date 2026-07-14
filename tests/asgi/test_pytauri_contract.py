"""pytauri 升级哨兵:断言 Protocol 依赖的结构面在真类上仍然存在。

pytauri 的 Python 包在无 Rust 扩展(ext_mod)的环境下 import 即抛 RuntimeError,
因此本模块在裸环境整体 skip;example(pytauri-wheel)环境中生效。
"""

import pytest

try:
    from pytauri.ffi.ipc import Channel, Invoke, InvokeResolver, JavaScriptChannelId
except Exception:  # noqa: BLE001 - ext_mod 缺失抛 RuntimeError 而非 ImportError
    pytest.skip(
        "pytauri runtime (ext_mod) unavailable; contract tests require a pytauri-wheel environment",
        allow_module_level=True,
    )


def test_invoke_surface() -> None:
    assert hasattr(Invoke, 'bind_to')
    assert hasattr(Invoke, 'command')
    assert hasattr(Invoke, 'reject')


def test_resolver_surface() -> None:
    assert hasattr(InvokeResolver, 'arguments')
    assert hasattr(InvokeResolver, 'resolve')
    assert hasattr(InvokeResolver, 'reject')


def test_channel_surface() -> None:
    assert hasattr(Channel, 'send')
    assert hasattr(JavaScriptChannelId, 'from_str')
    assert hasattr(JavaScriptChannelId, 'channel_on')
