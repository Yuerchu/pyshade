"""Each 循环容器(M2 Phase 6,design.md §3.3 模板所有权行)。

render-prop 构造期执行恰一次,收类型化 ItemProxy(lambda 合法——它不是事件 handler,
不进 EventRegistry),返回的模板树存 PrivateAttr。

数据流约定:items 只接受 ServerState 的 list 字段,整表替换驱动更新——原地
`chat.messages.append(msg)` 不经过描述符赋值,前端不会收到 patch;惯用法是
`chat.messages = [*chat.messages, msg]`。

所有权(§3.3 新行):模板内 plain prop 降级为构建期常量(发字面量,Update 拒绝
`.$t[` anchor);expr(含 ItemRef)/ServerRef 照常。模板事件共享 handlerId,
payload 自动携带 item_index(指定 key 时另带 item_key)。
"""

from collections.abc import Callable
from typing import Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel, Field, PrivateAttr

from pyshade.components.base import Component, TemplateContainer, read_anchor
from pyshade.expr import Expr, ExprType, ItemRef
from pyshade.state import ServerRef

_SCALAR_EXPR_TYPES: dict[object, ExprType] = {
    bool: ExprType.BOOL,
    int: ExprType.INT,
    float: ExprType.FLOAT,
    str: ExprType.STR,
}

_KEY_TYPES = (str, int)
"""key 字段允许的注解:React key 语义(bool/float 不做 key)。"""


class ItemProxy:
    """render 的入参(模型项):属性访问 → 按模型注解定型的 ItemRef,并 memoize
    (scope/snapshot 按身份哈希,同一字段必须复用同一叶子)。"""

    def __init__(self, model: type[BaseModel], token: object) -> None:
        self._model = model
        self._token = token
        self._refs: dict[str, ItemRef[Any]] = {}

    def __getattr__(self, name: str) -> Expr[Any]:
        # 实例属性(_model 等)走常规查找,不进此分支
        if name.startswith('_'):
            raise AttributeError(name)
        cached = self._refs.get(name)
        if cached is not None:
            return cached
        field = self._model.model_fields.get(name)
        if field is None:
            raise AttributeError(f"{self._model.__name__} 没有字段 '{name}';Each 项字段以模型注解为准")
        expr_type = _SCALAR_EXPR_TYPES[field.annotation]  # G-E1 已保证扁平标量
        ref: ItemRef[Any] = ItemRef(self._token, name, expr_type)
        self._refs[name] = ref
        return ref


def _resolve_item_type(items: ServerRef[Any]) -> tuple[type[BaseModel] | None, ExprType | None]:
    """G-E1:items 注解必须是 list[标量] 或 list[扁平 BaseModel](字段全标量)。"""
    owner = f'{items.state_class.__name__}.{items.field}'
    annotation: object = get_type_hints(items.state_class).get(items.field)
    if get_origin(annotation) is not list:
        raise TypeError(f"Each 的 items 需要 list 注解的 ServerState 字段(如 list[Message]),{owner} 是 {annotation!r}")
    (item_type,) = get_args(annotation)
    if item_type in _SCALAR_EXPR_TYPES:
        return None, _SCALAR_EXPR_TYPES[item_type]
    if isinstance(item_type, type) and issubclass(item_type, BaseModel):
        for name, field in item_type.model_fields.items():
            if field.annotation not in _SCALAR_EXPR_TYPES:
                raise TypeError(
                    f"Each 的项模型必须是扁平标量模型:{item_type.__name__}.{name} 的注解 "
                    f"{field.annotation!r} 不是 bool/int/float/str(嵌套结构 M3)"
                )
        return item_type, None
    raise TypeError(f"Each 的项类型只支持标量或扁平 BaseModel,{owner} 的项是 {item_type!r}")


class Each(Component, TemplateContainer):
    """列表渲染容器:`Each(ChatState.messages, render=lambda m: Text(m.text), key='id')`。

    - render 构造期执行一次;模型项收 ItemProxy(属性 → `Expr[Any]`,运行时按注解定型),
      标量项直接收 `Expr` 叶子;
    - key 缺省用索引;指定时必须是项模型的 str/int 字段;
    - 模板允许的组件与事件约束由编译期 G-E 规则把关(白名单 Text/Button/Card)。
    """

    _shade_tag = 'Each'

    items: ServerRef[Any] = Field(
        description="ServerState list field driving the template; replace the whole list to update.",
    )
    key: str | None = Field(
        default=None,
        description="Optional str/int field of the item model used as the React key; defaults to the index.",
    )

    _template_roots: list[Component] = PrivateAttr(default_factory=list[Component])
    _item_model: type[BaseModel] | None = PrivateAttr(default=None)
    _scalar_type: ExprType | None = PrivateAttr(default=None)
    _proxy: Any = PrivateAttr(default=None)
    _loop_token: object = PrivateAttr(default=None)

    def __init__(
        self,
        items: 'ServerRef[Any] | list[Any]',
        render: Callable[[Any], Component],
        *,
        key: str | None = None,
        visible: bool | Expr[bool] | ServerRef[bool] = True,
    ) -> None:
        # 静态层:ServerState 字段注解写裸 T(state.py 诚实类型),类访问在 pyright 眼中是
        # list[Model],故参数注解并上 list;运行时描述符保证真实值是 ServerRef
        if not isinstance(items, ServerRef):
            raise TypeError(
                f"Each 的 items 必须是 ServerState 的 list 字段(类访问,如 ChatState.messages),"
                f"收到 {type(items).__name__}"
            )
        item_model, scalar_type = _resolve_item_type(items)
        if key is not None:
            if item_model is None:
                raise TypeError("标量项的 Each 不支持 key(固定用索引);需要稳定 key 请改用扁平模型项")
            key_field = item_model.model_fields.get(key)
            if key_field is None:
                raise TypeError(f"key '{key}' 不是 {item_model.__name__} 的字段")
            if key_field.annotation not in _KEY_TYPES:
                raise TypeError(f"key 字段 {item_model.__name__}.{key} 必须是 str/int(React key 语义)")
        if not callable(render):
            raise TypeError("Each 的 render 必须是可调用对象(接收项代理,返回模板组件)")

        data: dict[str, Any] = {'items': items, 'key': key, 'visible': visible}
        super().__init__(**data)

        token = object()
        proxy: ItemProxy | ItemRef[Any]
        if item_model is not None:
            proxy = ItemProxy(item_model, token)
        else:
            assert scalar_type is not None
            proxy = ItemRef(token, '', scalar_type)
        template = render(proxy)
        if not isinstance(template, Component):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"Each 的 render 必须返回一个 Component(收到 {type(template).__name__})")
        if read_anchor(template) is not None:
            raise TypeError(f"Each 的模板组件已属于 {read_anchor(template)};模板必须在 render 内新建,不可复用页面组件")
        self._loop_token = token
        self._item_model = item_model
        self._scalar_type = scalar_type
        self._proxy = proxy
        self._template_roots = [template]


def item_model_of(each: Each) -> type[BaseModel] | None:
    """框架内部:项模型(标量项为 None)。"""
    return each._item_model  # pyright: ignore[reportPrivateUsage]


def item_scalar_type_of(each: Each) -> ExprType | None:
    """框架内部:标量项的 ExprType(模型项为 None)。"""
    return each._scalar_type  # pyright: ignore[reportPrivateUsage]


def loop_token_of(each: Each) -> object:
    """框架内部:该 Each 的归属标识(ItemRef 逃逸检测)。"""
    return each._loop_token  # pyright: ignore[reportPrivateUsage]


def iter_item_refs(each: Each) -> list[ItemRef[Any]]:
    """框架内部:该 Each 已物化的 ItemRef 叶子(模板中用过的字段;emit 注册 scope 用)。"""
    proxy: object = each._proxy  # pyright: ignore[reportPrivateUsage]
    if isinstance(proxy, ItemProxy):
        return list(proxy._refs.values())  # pyright: ignore[reportPrivateUsage]
    assert isinstance(proxy, ItemRef)
    return [proxy]


def item_snapshot(each: Each, item: object) -> dict[Expr[Any], object]:
    """双端对拍助手:把一个 item 的字段值绑定到该 Each 的 ItemRef 叶子,供 expr.evaluate()。

    模型项按模型字段取 getattr(item, 字段);标量项整个 item 即值。
    """
    model = item_model_of(each)
    proxy: object = each._proxy  # pyright: ignore[reportPrivateUsage]
    if model is not None:
        assert isinstance(proxy, ItemProxy)
        if not isinstance(item, model):
            raise TypeError(f"item 应为 {model.__name__},收到 {type(item).__name__}")
        return {getattr(proxy, name): getattr(item, name) for name in model.model_fields}
    assert isinstance(proxy, ItemRef)
    return {proxy: item}
