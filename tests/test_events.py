import functools
import json
from typing import Any, cast

import pytest
from pydantic import ValidationError

from pyshade.app import ShadeApp
from pyshade.asgi._bridge import RequestBridge
from pyshade.asgi._types import ChannelLike
from pyshade.asgi._wire import decode_envelope
from pyshade.components import Button, ButtonVariant, Card, Dialog, Handler, Input, TabItem, Tabs, Text
from pyshade.events import EventContext, EventHandlerError, EventRegistry, Update, validate_handler
from pyshade.expr import value_of
from pyshade.nav import navigate
from pyshade.page import Page
from pyshade.runtime import build_fastapi_app
from pyshade.state import ServerState
from tests.asgi.fakes import FakeChannel, make_invoke


def on_change(ctx: EventContext) -> None: ...


def on_submit(ctx: EventContext) -> list[Update]:
    name = str(ctx.values.get('username', ''))
    return [Update(DemoPage.greeting, text=f'hello {name}')]


async def on_async(ctx: EventContext) -> list[Update]:
    return [Update(DemoPage.greeting, text='async result')]


def bench_echo(ctx: EventContext) -> None: ...


def bad_bare_update(ctx: EventContext) -> Any:
    return Update(DemoPage.greeting, text='oops')  # 裸 Update:契约要求 list 包裹


def bad_string_return(ctx: EventContext) -> Any:
    return 'oops'


class DemoPage(Page):
    username = Input(label='用户名', on_change=on_change)
    submit = Button('登录', submit=True, on_click=on_submit)
    fire_async = Button('异步', on_click=on_async)
    greeting = Text('')

    card = Card(username, submit, fire_async, greeting)


def _demo_app() -> ShadeApp:
    return ShadeApp(pages=[DemoPage])


class TestUpdate:
    def test_valid_update_payload(self) -> None:
        update = Update(DemoPage.greeting, text='hi')
        assert update.to_payload() == {'target': 'DemoPage.greeting', 'props': {'text': 'hi'}}

    def test_enum_props_serialized_by_value(self) -> None:
        update = Update(DemoPage.submit, variant=ButtonVariant.DESTRUCTIVE)
        assert update.to_payload()['props'] == {'variant': 'destructive'}

    def test_unknown_prop_rejected(self) -> None:
        with pytest.raises(ValueError, match="没有 prop"):
            Update(DemoPage.greeting, nonexistent=1)

    def test_event_field_rejected(self) -> None:
        with pytest.raises(ValueError, match='事件字段'):
            Update(DemoPage.submit, on_click=on_change)

    def test_wrong_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Update(DemoPage.greeting, text=123)

    def test_original_component_untouched(self) -> None:
        Update(DemoPage.greeting, text='changed')
        text = DemoPage.greeting.text
        assert isinstance(text, str) and text == ''


class ReachState(ServerState):
    note: str = ''


class ReachPage(Page):
    plain_input = Input()  # label=None:可选 prop 构建期缺席
    labeled = Input(label='名字')
    hidden = Text('secret', visible=False)
    inner = Text('inner')
    box = Card(inner)
    opener = Button('open')
    body = Text('body')
    dlg = Dialog(body, trigger=opener, title='标题')
    tab_a = Text('a')
    tabs = Tabs(TabItem('A', tab_a))


class TestUpdateReachability:
    """构造期拒绝 patch 永远不可达的 prop 与非 plain 新值(发版前审查防线)。"""

    def test_structural_children_rejected(self) -> None:
        with pytest.raises(ValueError, match='结构 prop'):
            Update(ReachPage.box, children=[Text('new')])

    def test_structural_trigger_rejected(self) -> None:
        with pytest.raises(ValueError, match='结构 prop'):
            Update(ReachPage.dlg, trigger=Button('x'))

    def test_plain_controlled_value_rejected(self) -> None:
        with pytest.raises(ValueError, match='所有权在客户端'):
            Update(ReachPage.plain_input, value='new')

    def test_plain_controlled_tabs_rejected(self) -> None:
        with pytest.raises(ValueError, match='所有权在客户端'):
            Update(ReachPage.tabs, value='A')

    def test_plain_controlled_dialog_open_rejected(self) -> None:
        with pytest.raises(ValueError, match='所有权在客户端'):
            Update(ReachPage.dlg, open=True)

    def test_none_optional_prop_rejected(self) -> None:
        with pytest.raises(ValueError, match='rt.ov 锚点'):
            Update(ReachPage.plain_input, label='新标签')

    def test_const_marked_prop_rejected(self) -> None:
        with pytest.raises(ValueError, match='构建期常量'):
            Update(ReachPage.hidden, muted=True)

    def test_set_optional_prop_allowed(self) -> None:
        update = Update(ReachPage.labeled, label='改')
        assert update.to_payload()['props'] == {'label': '改'}

    def test_plain_visible_toggle_allowed(self) -> None:
        # 构建期 visible=False 的组件可被服务端翻转(guard 由编译器发射)
        update = Update(ReachPage.hidden, visible=True)
        assert update.to_payload()['props'] == {'visible': True}

    def test_expr_new_value_rejected(self) -> None:
        with pytest.raises(ValueError, match='客户端表达式'):
            Update(ReachPage.labeled, label=value_of(ReachPage.plain_input))

    def test_server_ref_new_value_rejected(self) -> None:
        with pytest.raises(ValueError, match='ServerState 字段引用'):
            Update(ReachPage.labeled, label=ReachState.note)

    def test_client_action_new_value_rejected(self) -> None:
        with pytest.raises(ValueError, match='客户端 action'):
            Update(ReachPage.labeled, label=navigate('DemoPage'))

    def test_component_new_value_rejected(self) -> None:
        with pytest.raises(ValueError, match='组件实例'):
            Update(ReachPage.labeled, label=Text('x'))

    def test_expr_inside_list_new_value_rejected(self) -> None:
        with pytest.raises(ValueError, match='客户端表达式'):
            Update(ReachPage.labeled, label=[value_of(ReachPage.plain_input)])


class TestValidateHandler:
    def test_module_level_function_ok(self) -> None:
        validate_handler(on_change, owner='x')

    def test_lambda_rejected(self) -> None:
        fn = cast('Handler', lambda ctx: None)  # noqa: E731  # pyright: ignore[reportUnknownLambdaType]
        with pytest.raises(EventHandlerError, match='lambda'):
            validate_handler(fn, owner='x')

    def test_local_function_rejected(self) -> None:
        def local(ctx: EventContext) -> None: ...

        with pytest.raises(EventHandlerError, match='模块级'):
            validate_handler(local, owner='x')

    def test_method_rejected(self) -> None:
        with pytest.raises(EventHandlerError, match='模块级'):
            validate_handler(TestValidateHandler.test_method_rejected, owner='x')

    def test_wrong_arity_rejected(self) -> None:
        with pytest.raises(EventHandlerError, match='一个位置参数'):
            validate_handler(_two_params, owner='x')

    def test_wrong_annotation_rejected(self) -> None:
        with pytest.raises(EventHandlerError, match='EventContext'):
            validate_handler(_wrong_annotation, owner='x')

    def test_partial_rejected(self) -> None:
        with pytest.raises(EventHandlerError, match='模块级 def'):
            validate_handler(cast('Handler', functools.partial(on_change)), owner='x')

    def test_class_rejected(self) -> None:
        with pytest.raises(EventHandlerError, match='模块级 def'):
            validate_handler(cast('Handler', _CallableProbe), owner='x')

    def test_callable_instance_rejected(self) -> None:
        with pytest.raises(EventHandlerError, match='模块级 def'):
            validate_handler(cast('Handler', _CallableProbe()), owner='x')


def _two_params(ctx: EventContext, extra: int) -> None: ...


def _wrong_annotation(ctx: int) -> None: ...


class _CallableProbe:
    def __call__(self, ctx: EventContext) -> None: ...


class TestEventRegistry:
    def test_collects_bound_handlers(self) -> None:
        registry = EventRegistry.from_app(_demo_app())
        assert set(registry) == {
            'DemoPage.username.on_change',
            'DemoPage.submit.on_click',
            'DemoPage.fire_async.on_click',
        }

    def test_entry_shape(self) -> None:
        registry = EventRegistry.from_app(_demo_app())
        entry = registry['DemoPage.submit.on_click']
        assert entry.handler is on_submit
        assert entry.kind == 'click'
        assert entry.submit is True
        assert registry['DemoPage.username.on_change'].submit is False

    def test_extra_handlers(self) -> None:
        registry = EventRegistry.from_app(_demo_app(), extra_handlers={'bench_echo': bench_echo})
        assert registry['bench_echo'].kind == 'extra'


class TestEventRouteContract:
    """接缝契约:事件走完整 ASGI over IPC 路径(RequestBridge + FakeInvoke)。"""

    def _bridge(self) -> RequestBridge:
        extras: dict[str, Handler] = {
            'bench_echo': bench_echo,
            'bare_update': bad_bare_update,
            'string_return': bad_string_return,
        }
        registry = EventRegistry.from_app(_demo_app(), extra_handlers=extras)
        fastapi_app = build_fastapi_app(registry)

        def factory(channel_id: str, webview_window: Any) -> ChannelLike:
            return FakeChannel()

        return RequestBridge(fastapi_app, channel_factory=factory, lifespan_state=lambda: None, bind_parameters={})

    def _dispatch(self, handler_id: str, payload: dict[str, Any]) -> tuple[int, Any]:
        import anyio

        bridge = self._bridge()
        invoke = make_invoke(
            'POST',
            f'/_shade/event/{handler_id}',
            body=json.dumps(payload).encode(),
            extra_headers=[(b'content-type', b'application/json')],
        )
        anyio.run(bridge.handle_invoke, invoke)
        value = invoke.resolver.resolved[0]
        assert isinstance(value, bytes)
        head, body = decode_envelope(value)
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body.decode('utf-8', errors='replace')
        return head.status, parsed

    def test_submit_returns_patches_envelope(self) -> None:
        status, body = self._dispatch('DemoPage.submit.on_click', {'values': {'username': 'yuerchu'}})
        assert status == 200
        assert body == {'patches': [{'target': 'DemoPage.greeting', 'props': {'text': 'hello yuerchu'}}]}

    def test_async_handler_supported(self) -> None:
        status, body = self._dispatch('DemoPage.fire_async.on_click', {})
        assert status == 200
        assert body['patches'][0]['props'] == {'text': 'async result'}

    def test_none_returning_handler_yields_empty_patches(self) -> None:
        status, body = self._dispatch('DemoPage.username.on_change', {'value': 'abc'})
        assert status == 200
        assert body == {'patches': []}

    def test_unknown_handler_404(self) -> None:
        status, _ = self._dispatch('DemoPage.nope.on_click', {})
        assert status == 404

    def test_invalid_payload_422(self) -> None:
        status, _ = self._dispatch('DemoPage.username.on_change', {'value': {'bad': 'type'}})
        assert status == 422

    def test_bench_echo_registered(self) -> None:
        status, body = self._dispatch('bench_echo', {})
        assert status == 200
        assert body == {'patches': []}

    def test_bare_update_return_500_with_hint(self) -> None:
        status, body = self._dispatch('bare_update', {})
        assert status == 500
        assert '单个 patch' in body['detail']

    def test_non_sequence_return_500(self) -> None:
        status, body = self._dispatch('string_return', {})
        assert status == 500
        assert 'list[Update | Navigate]' in body['detail']

    def test_no_docs_routes(self) -> None:
        registry = EventRegistry.from_app(_demo_app())
        fastapi_app = build_fastapi_app(registry)
        paths = [getattr(r, 'path', '') for r in fastapi_app.routes]
        assert '/docs' not in paths
        assert '/openapi.json' not in paths
