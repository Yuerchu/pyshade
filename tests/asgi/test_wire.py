import pytest

from pyshade.asgi._wire import (
    ENVELOPE_MAGIC,
    FRAME_BODY,
    FRAME_END,
    FRAME_ERROR,
    H_CHANNEL,
    H_METHOD,
    H_PATH,
    H_QUERY,
    RequestMeta,
    ResponseHead,
    WireError,
    decode_envelope,
    encode_body_frame,
    encode_end_frame,
    encode_envelope,
    encode_error_frame,
    encode_reject,
    parse_request_meta,
    strip_wire_headers,
)

# design.md §3.7 / 计划文档锁定的 golden 示例:GET /api/hello → 200 + {"msg":"hi"},共 82 字节
GOLDEN_HEAD = ResponseHead(status=200, headers=[(b'content-type', b'application/json')])
GOLDEN_BODY = b'{"msg":"hi"}'
GOLDEN_META = b'{"status":200,"headers":[["content-type","application/json"]]}'
GOLDEN_FRAME = ENVELOPE_MAGIC + (62).to_bytes(4, 'big') + GOLDEN_META + GOLDEN_BODY


class TestEnvelope:
    def test_golden_bytes(self) -> None:
        frame = encode_envelope(GOLDEN_HEAD, GOLDEN_BODY)
        assert frame == GOLDEN_FRAME
        assert len(frame) == 82

    def test_roundtrip(self) -> None:
        head, body = decode_envelope(GOLDEN_FRAME)
        assert head == GOLDEN_HEAD
        assert body == GOLDEN_BODY

    def test_stream_flag_roundtrip(self) -> None:
        head = ResponseHead(status=200, headers=[], stream=True)
        decoded, body = decode_envelope(encode_envelope(head, b''))
        assert decoded.stream is True
        assert body == b''

    def test_stream_flag_omitted_when_false(self) -> None:
        assert b'stream' not in encode_envelope(GOLDEN_HEAD, b'')

    def test_multi_headers_and_utf8_body(self) -> None:
        head = ResponseHead(
            status=418,
            headers=[(b'x-a', b'1'), (b'x-a', b'2'), (b'content-type', b'text/plain; charset=utf-8')],
        )
        body = '你好'.encode()
        decoded, decoded_body = decode_envelope(encode_envelope(head, body))
        assert decoded == head
        assert decoded_body == body

    def test_latin1_header_bytes_survive(self) -> None:
        head = ResponseHead(status=200, headers=[(b'x-raw', bytes(range(0x20, 0xFF)))])
        decoded, _ = decode_envelope(encode_envelope(head, b''))
        assert decoded.headers == head.headers

    @pytest.mark.parametrize(
        'frame',
        [
            b'',
            b'PSA',
            b'XXXX' + (0).to_bytes(4, 'big'),
            ENVELOPE_MAGIC + (999).to_bytes(4, 'big') + b'{}',
            ENVELOPE_MAGIC + (2).to_bytes(4, 'big') + b'{}',
            ENVELOPE_MAGIC + (9).to_bytes(4, 'big') + b'not json!',
        ],
    )
    def test_malformed_frames(self, frame: bytes) -> None:
        with pytest.raises(WireError) as exc_info:
            decode_envelope(frame)
        assert exc_info.value.code == 'bad_envelope'


class TestRequestMeta:
    def test_full_parse(self) -> None:
        meta = parse_request_meta(
            [
                (H_METHOD, b'POST'),
                (H_PATH, b'/api/todos/%E4%B8%AD'),
                (H_QUERY, b'a=1&b=2'),
                (H_CHANNEL, b'__CHANNEL__:1234'),
                (b'content-type', b'application/json'),
            ]
        )
        assert meta == RequestMeta(
            method='POST',
            raw_path=b'/api/todos/%E4%B8%AD',
            query_string=b'a=1&b=2',
            channel_id='__CHANNEL__:1234',
        )

    def test_defaults(self) -> None:
        meta = parse_request_meta([(H_METHOD, b'GET'), (H_PATH, b'/')])
        assert meta.query_string == b''
        assert meta.channel_id is None

    @pytest.mark.parametrize('missing', [H_METHOD, H_PATH])
    def test_missing_required_header(self, missing: bytes) -> None:
        headers = [(k, b'x') for k in (H_METHOD, H_PATH) if k != missing]
        with pytest.raises(WireError) as exc_info:
            parse_request_meta(headers)
        assert exc_info.value.code == 'bad_request_meta'

    def test_first_value_wins(self) -> None:
        meta = parse_request_meta([(H_METHOD, b'GET'), (H_METHOD, b'POST'), (H_PATH, b'/')])
        assert meta.method == 'GET'


class TestStripWireHeaders:
    def test_strips_all_wire_headers(self) -> None:
        kept = strip_wire_headers(
            [
                (H_METHOD, b'GET'),
                (H_PATH, b'/'),
                (H_QUERY, b''),
                (H_CHANNEL, b'c'),
                (b'x-pyshade-future', b'1'),
                (b'content-type', b'application/json'),
                (b'x-custom', b'ok'),
            ]
        )
        assert kept == [(b'content-type', b'application/json'), (b'x-custom', b'ok')]


class TestFrames:
    def test_body_frame(self) -> None:
        assert encode_body_frame(b'data: 1\n\n') == bytes((FRAME_BODY,)) + b'data: 1\n\n'

    def test_end_frame(self) -> None:
        assert encode_end_frame() == bytes((FRAME_END,))

    def test_error_frame_golden(self) -> None:
        frame = encode_error_frame('app_error', 'boom')
        assert frame == bytes((FRAME_ERROR,)) + b'{"code":"app_error","message":"boom"}'


class TestReject:
    def test_reject_payload_golden(self) -> None:
        assert encode_reject('bad_request_meta', 'missing header') == (
            '{"code":"bad_request_meta","message":"missing header"}'
        )
