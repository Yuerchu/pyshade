"""双状态模型(design.md §3.3)— ServerState 侧。

ClientState 见 expr.ClientVal(声明为 Page 字段,编译进前端)。ServerState 是任意
Python:字段赋值即校验 + 自动 diff——事件请求内记入 contextvar sink,随响应下发;
请求外(后台任务)交给推送通道(M1 Phase 4,当前仅 debug 日志)。

关键机制:

- `ServerField[T]` 数据描述符:类访问 → `ServerRef[T]`(绑定引用,编译为
  `rt.ov("$s:类名", 字段, 默认)`),实例访问 → 纯 `T`,赋值 → TypeAdapter 校验 + dirty 分发。
  注解写裸 `T`(诚实类型:实例语义精确),描述符由 `__init_subclass__` 运行期替换。
- 单例:页面绑定按类名寻址(`$s:` 命名空间),多实例无从区分,二次实例化 RuntimeError。
- sink 带 closed 标志:spawn 的后台任务继承 contextvar 快照,请求结束后写入
  必须走推送通道而非已定稿的响应。
"""

import json
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, ClassVar, Generic, NoReturn, TypeVar, cast, get_origin, overload

from loguru import logger as l
from pydantic import GetCoreSchemaHandler, TypeAdapter
from pydantic_core import CoreSchema, core_schema, to_jsonable_python

T = TypeVar('T')

SERVER_NAMESPACE_PREFIX = '$s:'


class ServerStateError(Exception):
    """ServerState 类定义非法:缺默认值、默认值不可 JSON 序列化、类名冲突等。"""


class ServerRef(Generic[T]):
    """ServerState 字段的绑定引用(类访问产物)。

    不是表达式:值经服务端 patch 到达前端(rt.ov 可达),不参与客户端内联 JS;
    比较/布尔运算直接抛错,防止 `ChatState.status == 'x'` 被误当条件。
    """

    __slots__ = ('state_class', 'field', 'default')

    def __init__(self, state_class: 'type[ServerState]', field: str, default: T) -> None:
        self.state_class = state_class
        self.field = field
        self.default = default

    @property
    def target(self) -> str:
        """patch 与 rt.ov 的寻址锚点,如 '$s:ChatState'。"""
        return f'{SERVER_NAMESPACE_PREFIX}{self.state_class.__name__}'

    @classmethod
    def __get_pydantic_core_schema__(cls, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        # 组件 prop 注解 `T | ServerRef[T]` 按 isinstance 校验;类型匹配由编译器 checks 把关
        return core_schema.is_instance_schema(cls)

    def __eq__(self, other: object) -> NoReturn:
        raise TypeError(
            "ServerRef 不支持比较/逻辑运算:服务端逻辑请用实例访问(如 chat.status == 'x'),"
            "客户端联动请用 ClientVal 表达式(design.md §3.3)"
        )

    __hash__ = object.__hash__

    def __bool__(self) -> NoReturn:
        raise TypeError("ServerRef 不能用于布尔上下文;服务端逻辑请用实例访问(如 if chat.ready:)")

    def __repr__(self) -> str:
        return f'ServerRef({self.target}.{self.field}, default={self.default!r})'


class ServerField(Generic[T]):
    """数据描述符:类访问 → ServerRef[T],实例访问 → T,赋值 → 校验 + auto-diff。"""

    __slots__ = ('name', 'default', 'adapter', 'ref')

    def __init__(self, name: str, owner: 'type[ServerState]', default: T, adapter: TypeAdapter[T]) -> None:
        self.name = name
        self.default = default
        self.adapter = adapter
        self.ref: ServerRef[T] = ServerRef(owner, name, default)

    @overload
    def __get__(self, obj: None, objtype: 'type[ServerState]') -> 'ServerRef[T]': ...
    @overload
    def __get__(self, obj: 'ServerState', objtype: 'type[ServerState]') -> T: ...
    def __get__(self, obj: 'ServerState | None', objtype: 'type[ServerState] | None' = None) -> 'ServerRef[T] | T':
        if obj is None:
            return self.ref
        return cast('T', obj.__dict__[self.name])

    def __set__(self, obj: 'ServerState', value: T) -> None:
        validated = self.adapter.validate_python(value)  # 类型不符抛 ValidationError
        obj.__dict__[self.name] = validated
        _dispatch_dirty(self.ref, validated)


_STATE_CLASSES: dict[str, 'type[ServerState]'] = {}


def _register_state_class(cls: 'type[ServerState]') -> None:
    existing = _STATE_CLASSES.get(cls.__name__)
    if existing is not None and existing is not cls:
        raise ServerStateError(
            f"ServerState 类名冲突:{cls.__name__} 已在 {existing.__module__} 注册;$s: 命名空间按类名寻址,请改名"
        )
    _STATE_CLASSES[cls.__name__] = cls


class ServerState:
    """服务端状态基类:子类类体注解即字段(必须带 JSON 可序列化默认值),单例。

    非 BaseModel(描述符与 ModelMetaclass 冲突);字段校验用缓存 TypeAdapter。
    """

    _instance: ClassVar['ServerState | None'] = None
    __shade_fields__: ClassVar[dict[str, 'ServerField[Any]']] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        annotations = cast('dict[str, Any]', vars(cls).get('__annotations__', {}))
        fields: dict[str, ServerField[Any]] = {}
        for name, annotation in annotations.items():
            if name.startswith('_') or annotation is ClassVar or get_origin(annotation) is ClassVar:
                continue
            if name not in vars(cls):
                raise ServerStateError(
                    f"{cls.__name__}.{name} 缺少默认值;ServerState 字段必须提供默认值(前端快照的初始值)"
                )
            default: Any = vars(cls)[name]
            try:
                json.dumps(to_jsonable_python(default))
            except Exception as exc:
                raise ServerStateError(f"{cls.__name__}.{name} 默认值不可 JSON 序列化:{exc}") from exc
            adapter: TypeAdapter[Any] = TypeAdapter(annotation)
            validated_default: Any = adapter.validate_python(default)
            server_field: ServerField[Any] = ServerField(name, cls, validated_default, adapter)
            setattr(cls, name, server_field)
            fields[name] = server_field
        cls.__shade_fields__ = fields
        cls._instance = None
        _register_state_class(cls)

    def __init__(self) -> None:
        cls = type(self)
        if cls._instance is not None:
            raise RuntimeError(f"{cls.__name__} 是单例,已在别处实例化;请 import 复用该实例")
        cls._instance = self
        # 初始化只落值,不触发 dirty 分发(绕过描述符 __set__)
        for name, server_field in cls.__shade_fields__.items():
            self.__dict__[name] = server_field.default


@dataclass
class PatchSink:
    """事件请求内的 auto-diff 收集器;同字段多次赋值最后一次生效。"""

    closed: bool = False
    _values: dict[tuple[str, str], Any] = dc_field(default_factory=dict[tuple[str, str], Any])

    def record(self, ref: 'ServerRef[Any]', value: object) -> None:
        self._values[(ref.target, ref.field)] = value

    def to_patches(self) -> list[dict[str, Any]]:
        """按 target 聚合成 patch 列表(与 Update.to_payload 同构)。"""
        by_target: dict[str, dict[str, Any]] = {}
        for (target, field_name), value in self._values.items():
            by_target.setdefault(target, {})[field_name] = to_jsonable_python(value)
        return [{'target': target, 'props': props} for target, props in by_target.items()]


_SINK: ContextVar[PatchSink | None] = ContextVar('pyshade_patch_sink', default=None)


@contextmanager
def patch_sink() -> Generator[PatchSink, None, None]:
    """事件请求包裹:期间的 ServerState 赋值记入 sink;退出即 closed。

    spawn 的后台任务继承 contextvar 快照仍能看到此 sink,closed 标志确保
    请求定稿后的写入不再进入已发出的响应。
    """
    sink = PatchSink()
    token = _SINK.set(sink)
    try:
        yield sink
    finally:
        sink.closed = True
        _SINK.reset(token)


DirtyPublisher = Callable[['ServerRef[Any]', Any], None]

_publisher: DirtyPublisher | None = None


def set_dirty_publisher(publisher: DirtyPublisher | None) -> None:
    """框架内部:注册请求外变更的去处(push.PatchBus);None 恢复未接线状态。"""
    global _publisher
    _publisher = publisher


def server_state_snapshot() -> list[dict[str, Any]]:
    """全部已实例化 ServerState 的当前值(patch 形态);SSE 订阅时先推全量快照,
    解决页面加载晚于变更与重连丢帧,免去 patch 序号机制。"""
    patches: list[dict[str, Any]] = []
    for cls in _STATE_CLASSES.values():
        instance = cls._instance  # pyright: ignore[reportPrivateUsage]
        if instance is None or not cls.__shade_fields__:
            continue
        props = {name: to_jsonable_python(instance.__dict__[name]) for name in cls.__shade_fields__}
        patches.append({'target': f'{SERVER_NAMESPACE_PREFIX}{cls.__name__}', 'props': props})
    return patches


def _dispatch_dirty(ref: 'ServerRef[Any]', value: object) -> None:
    sink = _SINK.get()
    if sink is not None and not sink.closed:
        sink.record(ref, value)
        return
    # 请求外变更(后台任务/启动逻辑):交给推送通道
    if _publisher is not None:
        _publisher(ref, value)
        return
    l.debug("pyshade.state: {}.{} 在事件请求外变更且推送通道未接线,变更仅落在服务端", ref.target, ref.field)
