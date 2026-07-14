from pyshade.asgi._bridge import build_http_scope
from pyshade.asgi._wire import H_CHANNEL, H_METHOD, H_PATH, RequestMeta


def _meta(**overrides: object) -> RequestMeta:
    defaults: dict[str, object] = {'method': 'GET', 'raw_path': b'/', 'query_string': b'', 'channel_id': None}
    defaults.update(overrides)
    return RequestMeta(**defaults)  # type: ignore[arg-type]


class TestBuildHttpScope:
    def test_field_by_field(self) -> None:
        meta = RequestMeta(method='POST', raw_path=b'/api/x', query_string=b'a=1', channel_id='c')
        scope = build_http_scope(meta, [(b'content-type', b'application/json')])
        assert scope['type'] == 'http'
        assert scope['asgi'] == {'version': '3.0', 'spec_version': '2.3'}
        assert scope['http_version'] == '1.1'
        assert scope['method'] == 'POST'
        assert scope['scheme'] == 'http'
        assert scope['path'] == '/api/x'
        assert scope['raw_path'] == b'/api/x'
        assert scope['query_string'] == b'a=1'
        assert scope['root_path'] == ''
        assert scope['headers'] == [(b'content-type', b'application/json')]
        assert scope['client'] == ('ipc', 0)
        assert scope['server'] == ('pyshade', None)
        assert 'state' not in scope
        assert 'extensions' not in scope

    def test_percent_decoded_path(self) -> None:
        scope = build_http_scope(_meta(raw_path=b'/api/todos/%E4%B8%AD%20x'), [])
        assert scope['path'] == '/api/todos/中 x'
        assert scope['raw_path'] == b'/api/todos/%E4%B8%AD%20x'

    def test_wire_headers_stripped(self) -> None:
        headers = [
            (H_METHOD, b'GET'),
            (H_PATH, b'/'),
            (H_CHANNEL, b'c'),
            (b'x-pyshade-anything', b'1'),
            (b'x-custom', b'ok'),
        ]
        scope = build_http_scope(_meta(), headers)
        assert scope['headers'] == [(b'x-custom', b'ok')]

    def test_state_is_shallow_copied(self) -> None:
        state = {'db': 'conn'}
        scope = build_http_scope(_meta(), [], state=state)
        assert scope['state'] == {'db': 'conn'}
        scope['state']['db'] = 'other'
        assert state['db'] == 'conn'

    def test_extensions_passthrough(self) -> None:
        ext = {'pyshade.ipc': {'webview_window': object()}}
        scope = build_http_scope(_meta(), [], extensions=ext)
        assert scope['extensions'] is ext
