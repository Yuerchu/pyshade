"""wire 协议纯函数层(design.md §3.7)。

请求 HTTP 语义经 `x-pyshade-*` headers 编码;单帧响应为 PSA1 二进制封包;
流式响应经 Channel 以 tag 字节前缀分帧。本模块零 pytauri 依赖,
协议由 golden bytes 测试锁定,前端 `frontend/src/ipc/wire.ts` 与此镜像。
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

ASGI_COMMAND: Final = '__pyshade_asgi__'
"""pyfunc header 的固定哨兵值:标识一次 ASGI over IPC 请求。"""

ENVELOPE_MAGIC: Final = b'PSA1'

H_METHOD: Final = b'x-pyshade-method'
H_PATH: Final = b'x-pyshade-path'
H_QUERY: Final = b'x-pyshade-query'
H_CHANNEL: Final = b'x-pyshade-channel'
WIRE_HEADER_PREFIX: Final = b'x-pyshade-'

FRAME_BODY: Final = 0x02
FRAME_END: Final = 0x03
FRAME_ERROR: Final = 0x04
# 0x01 与 0x10-0x1F 保留(未来 start 帧 / WebSocket 语义)。


class WireError(Exception):
    """传输层协议错误;code 即 reject 载荷错误码。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class RequestMeta:
    """从 wire headers 解出的请求元数据。"""

    method: str
    raw_path: bytes
    query_string: bytes = b''
    channel_id: str | None = None


def _decode_ascii_meta(value: bytes, header_name: str) -> str:
    """meta header 解码防线:非 ASCII 字节转 WireError,保证 invoke 必被应答
    (裸 UnicodeDecodeError 会逃出 except WireError,resolver 悬空)。"""
    try:
        return value.decode('ascii')
    except UnicodeDecodeError as exc:
        raise WireError('bad_request_meta', f"{header_name} header is not valid ASCII") from exc


def parse_request_meta(headers: Sequence[tuple[bytes, bytes]]) -> RequestMeta:
    """解析 x-pyshade-* 元数据 headers;缺失/非 ASCII 抛 WireError('bad_request_meta')。"""
    method: str | None = None
    raw_path: bytes | None = None
    query_string = b''
    channel_id: str | None = None
    for key, value in headers:
        if key == H_METHOD and method is None:
            method = _decode_ascii_meta(value, 'x-pyshade-method')
        elif key == H_PATH and raw_path is None:
            raw_path = value
        elif key == H_QUERY and not query_string:
            query_string = value
        elif key == H_CHANNEL and channel_id is None:
            channel_id = _decode_ascii_meta(value, 'x-pyshade-channel')
    if method is None:
        raise WireError('bad_request_meta', "missing x-pyshade-method header")
    if raw_path is None:
        raise WireError('bad_request_meta', "missing x-pyshade-path header")
    return RequestMeta(method=method, raw_path=raw_path, query_string=query_string, channel_id=channel_id)


def strip_wire_headers(headers: Sequence[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """剥掉全部 x-pyshade-* 传输层 headers,应用层不可见。"""
    return [(k, v) for k, v in headers if not k.startswith(WIRE_HEADER_PREFIX)]


@dataclass(frozen=True, slots=True)
class ResponseHead:
    """响应封包的 meta 部分。"""

    status: int
    headers: list[tuple[bytes, bytes]] = field(default_factory=list[tuple[bytes, bytes]])
    stream: bool = False


def encode_envelope(head: ResponseHead, body: bytes) -> bytes:
    """单帧响应封包:PSA1 + u32(meta_len, 大端) + meta JSON + body。

    headers 的 bytes 以 latin-1 映射进 JSON 字符串(HTTP header 语义,任意字节可逆)。
    """
    meta: dict[str, object] = {
        'status': head.status,
        'headers': [[k.decode('latin-1'), v.decode('latin-1')] for k, v in head.headers],
    }
    if head.stream:
        meta['stream'] = True
    meta_bytes = json.dumps(meta, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return ENVELOPE_MAGIC + len(meta_bytes).to_bytes(4, 'big') + meta_bytes + body


def decode_envelope(frame: bytes) -> tuple[ResponseHead, bytes]:
    """encode_envelope 的逆;畸形帧抛 WireError('bad_envelope')。测试与 dev 工具用。"""
    if len(frame) < 8 or frame[:4] != ENVELOPE_MAGIC:
        raise WireError('bad_envelope', "invalid envelope magic")
    meta_len = int.from_bytes(frame[4:8], 'big')
    if len(frame) < 8 + meta_len:
        raise WireError('bad_envelope', "envelope meta truncated")
    try:
        meta = json.loads(frame[8 : 8 + meta_len].decode('utf-8'))
        status = meta['status']
        raw_headers = meta['headers']
        stream = bool(meta.get('stream', False))
        if not isinstance(status, int):
            raise TypeError
        headers = [(k.encode('latin-1'), v.encode('latin-1')) for k, v in raw_headers]
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise WireError('bad_envelope', "envelope meta is not valid") from exc
    return ResponseHead(status=status, headers=headers, stream=stream), frame[8 + meta_len :]


def encode_body_frame(chunk: bytes) -> bytes:
    return bytes((FRAME_BODY,)) + chunk


def encode_end_frame() -> bytes:
    return bytes((FRAME_END,))


def encode_error_frame(code: str, message: str) -> bytes:
    payload = json.dumps({'code': code, 'message': message}, separators=(',', ':'), ensure_ascii=False)
    return bytes((FRAME_ERROR,)) + payload.encode('utf-8')


def encode_reject(code: str, message: str) -> str:
    """传输层错误的 reject 载荷(JSON 字符串)。"""
    return json.dumps({'code': code, 'message': message}, separators=(',', ':'), ensure_ascii=False)
