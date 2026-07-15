"""事件模型与注册表(计划 Part B 事件模型)。

handler 统一签名 `(ctx: EventContext) -> list[Update] | None`(同步或 async);
必须是模块级具名 callable——lambda/闭包/方法无法被 EventRegistry 稳定重建。
handlerId 与编译器共用 `pyshade.page.anchor_of`,两端不会漂移。
"""

import inspect
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

from pydantic import BaseModel

from pyshade.app import ShadeApp
from pyshade.components.base import Component, EventSpec, Handler
from pyshade.expr import Expr
from pyshade.nav import NavigateAction
from pyshade.page import Page, anchor_of, iter_nodes
from pyshade.state import ServerRef


class EventHandlerError(Exception):
    """事件 handler 不符合约束(编译期/注册期报错)。"""


class EventContext(BaseModel):
    """事件回传给 Python handler 的统一入参。

    values:页面命名输入的快照(含 ClientVal 条目,数值型 ClientVal 为 int/float);
    敏感值仅 submit=True 的事件携带(design.md §3.8)。
    value:change 类事件的新值。
    item_index/item_key:Each 模板事件自动携带(M2 Phase 6);key 未指定时 item_key 为 None。
    """

    values: dict[str, str | bool | int | float] = {}
    value: str | bool | int | float | None = None
    item_index: int | None = None
    item_key: str | int | None = None


class Update:
    """handler 返回值:目标组件的 props patch;构造时即校验键与类型。"""

    def __init__(self, target: Component, **props: Any) -> None:
        self.target = anchor_of(target)  # 未挂 Page 时抛 LayoutError
        if '.$t[' in self.target:
            # 所有权公理(design.md §3.3 模板行):模板 plain prop 是构建期常量
            raise ValueError(
                f"{self.target} 在 Each 模板内:模板 plain prop 是构建期常量,不能 Update;"
                "列表内容请整表替换 ServerState 字段(如 chat.messages = [*chat.messages, msg])"
            )
        fields = type(target).model_fields
        probe = target.model_copy()
        validator = type(target).__pydantic_validator__
        for key, value in props.items():
            if key not in fields:
                raise ValueError(f"{type(target).__name__} 没有 prop '{key}',无法 Update")
            if any(isinstance(m, EventSpec) for m in fields[key].metadata):
                raise ValueError(f"事件字段 '{key}' 不能通过 Update 修改")
            current: object = getattr(target, key)
            if isinstance(current, Expr):
                # 所有权公理(design.md §3.4):Expr 绑定的 prop 归客户端所有,服务端 patch 是编程错误
                raise ValueError(
                    f"{self.target}.{key} 已绑定客户端表达式(所有权在客户端),不能通过 Update 修改;"
                    "需要服务端控制请改用普通值 + Update,或绑定 ServerState 字段"
                )
            if isinstance(current, ServerRef):
                raise ValueError(
                    f"{self.target}.{key} 已绑定 ServerState 字段({current.target}.{current.field}),"
                    "请直接给该字段赋值(自动 diff),不要用 Update"
                )
            validator.validate_assignment(probe, key, value)  # 类型不符抛 ValidationError
        self.props = props

    def to_payload(self) -> dict[str, Any]:
        def jsonify(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, BaseModel):
                return value.model_dump(mode='json')
            if isinstance(value, (list, tuple)):
                return [jsonify(item) for item in cast('list[object]', value)]
            return value

        props = {key: jsonify(value) for key, value in self.props.items()}
        return {'target': self.target, 'props': props}


def validate_handler(handler: Handler, *, owner: str) -> None:
    """校验事件 handler:模块级具名、恰一个位置参数、参数注解(若有)为 EventContext。

    返回注解不在此校验(形态多样),交由用户侧 pyright 覆盖。
    """
    name = getattr(handler, '__name__', '')
    qualname = getattr(handler, '__qualname__', '')
    if name == '<lambda>':
        raise EventHandlerError(f"{owner} 的 handler 不能是 lambda,请使用模块级具名函数")
    if '<locals>' in qualname or '.' in qualname:
        raise EventHandlerError(
            f"{owner} 的 handler 必须是模块级函数(当前 {qualname!r});闭包/方法无法被 EventRegistry 稳定重建"
        )
    signature = inspect.signature(handler)
    positional = [
        p
        for p in signature.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    required_keyword = [
        p
        for p in signature.parameters.values()
        if p.kind == inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty
    ]
    if len(positional) != 1 or required_keyword:
        raise EventHandlerError(f"{owner} 的 handler 必须恰好接受一个位置参数 (ctx: EventContext)")
    annotation = positional[0].annotation
    if annotation is not inspect.Parameter.empty and annotation not in (EventContext, 'EventContext'):
        raise EventHandlerError(f"{owner} 的 handler 参数注解必须是 EventContext(当前 {annotation!r})")


@dataclass(frozen=True, slots=True)
class EventEntry:
    """一个已注册事件:handlerId → handler 与其上下文。"""

    handler_id: str
    handler: Handler
    kind: str
    component: Component | None
    submit: bool
    page: type[Page] | None


class EventRegistry(Mapping[str, EventEntry]):
    """handlerId → EventEntry;asgi 层据此挂载 /_shade/event/{handler_id} 路由。"""

    def __init__(self, entries: dict[str, EventEntry], *, page_names: frozenset[str] = frozenset()) -> None:
        self._entries = entries
        self.page_names = page_names
        """app 的页面类名集合;dispatch 校验服务端 Navigate 目标(空集 = 不校验,手工构造场景)。"""

    def __getitem__(self, key: str) -> EventEntry:
        return self._entries[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    @classmethod
    def from_app(cls, app: ShadeApp, *, extra_handlers: dict[str, Handler] | None = None) -> 'EventRegistry':
        """遍历 app 页面树收集事件绑定;与编译器共用同一份树遍历。

        extra_handlers:不挂组件的附加 handler(如基准测试的 bench_echo)。
        """
        entries: dict[str, EventEntry] = {}
        for page in app.pages:
            for component in iter_nodes(page):
                for field_name, field in type(component).model_fields.items():
                    specs = [m for m in field.metadata if isinstance(m, EventSpec)]
                    if not specs:
                        continue
                    handler: Handler | None = getattr(component, field_name)
                    if handler is None or isinstance(handler, NavigateAction):
                        continue  # navigate 编译为 rt.navigate,零 IPC,不进注册表
                    handler_id = f'{anchor_of(component)}.{field_name}'
                    validate_handler(handler, owner=handler_id)
                    submit = bool(getattr(component, 'submit', False))
                    entries[handler_id] = EventEntry(
                        handler_id=handler_id,
                        handler=handler,
                        kind=specs[0].kind,
                        component=component,
                        submit=submit,
                        page=page,
                    )
        for handler_id, handler in (extra_handlers or {}).items():
            validate_handler(handler, owner=handler_id)
            entries[handler_id] = EventEntry(
                handler_id=handler_id, handler=handler, kind='extra', component=None, submit=False, page=None
            )
        return cls(entries, page_names=frozenset(page.__name__ for page in app.pages))
