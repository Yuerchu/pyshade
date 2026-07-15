"""表达式系统(design.md §3.4):SQLAlchemy 式运算符重载构建表达式树。

纯叶子模块:不 runtime-import pyshade 其他模块(value_of 对 components 的引用
走 TYPE_CHECKING + 函数内惰性 import)。三条纪律:

- 构造期定型:每个节点构造时确定 ExprType,类型不符立即 TypeError(不等到编译);
  `&`/`|` 要求操作数为 bool 是优先级坑的第一道防线(`a == b & c` 先算 `b & c`)。
- `__bool__`/`__len__`/`__iter__`/`__contains__` 全部抛错:表达式进入 Python 布尔
  上下文(if/and/or/not/链式比较)没有合法语义,这是第二道防线。
- 双端求值:`to_js(scope)` 编译期翻译成 JS;`evaluate(snapshot)` 在 Python 侧按同一
  语义求值,测试无需起 WebView 即可验证两端一致。

`__eq__` 重载后以 `__hash__ = object.__hash__` 恢复身份哈希(SQLAlchemy 同款):
id 派生的哈希对不同对象必不相同,dict 探测先比完整哈希再比相等,因此以叶子节点为键的
scope/snapshot 字典永远不会触发 `__eq__` → `__bool__` 连锁。
"""

import json
import math
import operator
from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, Literal, NoReturn, TypeVar, cast, overload

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

if TYPE_CHECKING:
    from pyshade.components.base import Component, ControlledMixin

T = TypeVar('T')
_OrderedT = TypeVar('_OrderedT', int, float, str)

_BOOL_CONTEXT_HINT = (
    "Expr 不能用于 Python 布尔上下文(if/while/and/or/not/链式比较):"
    "逻辑运算请改用 & | ~ 并给比较加括号,如 (a == b) & (c != d);"
    "链式比较请拆成 (a < b) & (b < c);字面量在左侧导致类型推导退化时用 pyshade.expr.cond() 收窄;"
    "测试中要取真值请用 expr.evaluate(snapshot)"
)


class ExprType(Enum):
    """表达式的构造期类型;JSON/JS 可表达的四种标量。"""

    BOOL = 'bool'
    STR = 'str'
    INT = 'int'
    FLOAT = 'float'


_NUMERIC = frozenset({ExprType.INT, ExprType.FLOAT})

_CompareOp = Literal['==', '!=', '<', '<=', '>', '>=']
_BoolOpKind = Literal['and', 'or']

_JS_BOOL_OP: dict[str, str] = {'and': '&&', 'or': '||'}
_JS_COMPARE: dict[str, str] = {'==': '===', '!=': '!==', '<': '<', '<=': '<=', '>': '>', '>=': '>='}
_PY_COMPARE: dict[str, Any] = {
    '==': operator.eq,
    '!=': operator.ne,
    '<': operator.lt,
    '<=': operator.le,
    '>': operator.gt,
    '>=': operator.ge,
}


def _infer_type(value: object, *, owner: str) -> ExprType:
    """从 Python 值推导 ExprType;bool 先于 int 判定(bool 是 int 子类)。"""
    if isinstance(value, bool):
        return ExprType.BOOL
    if isinstance(value, int):
        return ExprType.INT
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"{owner} 不支持非有限 float(inf/nan 进不了 JSON/JS)")
        return ExprType.FLOAT
    if isinstance(value, str):
        return ExprType.STR
    raise TypeError(f"{owner} 只支持 bool/int/float/str,收到 {type(value).__name__}")


def _js_literal(value: object) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


class Expr(Generic[T]):
    """表达式树基类(不可变);仅由运算符、ClientVal、value_of、cond 构造。

    self-type 约束让 pyright 在错误类型上直接报错(如对 Expr[str] 调 `~`);
    运行时的 _require_* 检查是无类型代码的兜底防线。
    """

    __slots__ = ()

    type: ExprType

    @classmethod
    def __get_pydantic_core_schema__(cls, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        # 组件 prop 注解 `T | Expr[T]` 时按 isinstance 校验(泛型参数不参与运行时校验,
        # 表达式与 prop 的类型匹配由编译器 checks 把关)。
        # 已知边界:is_instance schema 无法进 model_json_schema(),M4 文档化组件 schema 前解决。
        return core_schema.is_instance_schema(cls)

    # ---- 逻辑运算(仅 BOOL) ----

    def __invert__(self: 'Expr[bool]') -> 'Expr[bool]':
        return UnaryNot(_require_bool(self, '~'))

    def __and__(self: 'Expr[bool]', other: 'Expr[bool] | bool') -> 'Expr[bool]':
        return BoolOp('and', _require_bool(self, '&'), _coerce_bool_operand(other, '&'))

    def __rand__(self: 'Expr[bool]', other: bool) -> 'Expr[bool]':
        return BoolOp('and', _coerce_bool_operand(other, '&'), _require_bool(self, '&'))

    def __or__(self: 'Expr[bool]', other: 'Expr[bool] | bool') -> 'Expr[bool]':
        return BoolOp('or', _require_bool(self, '|'), _coerce_bool_operand(other, '|'))

    def __ror__(self: 'Expr[bool]', other: bool) -> 'Expr[bool]':
        return BoolOp('or', _coerce_bool_operand(other, '|'), _require_bool(self, '|'))

    # ---- 相等比较(任意同类别)与身份哈希 ----

    def __eq__(self, other: object) -> 'Expr[bool]':  # pyright: ignore[reportIncompatibleMethodOverride]
        return Compare('==', self, _coerce_compare_operand(other, like=self, op='=='))

    def __ne__(self, other: object) -> 'Expr[bool]':  # pyright: ignore[reportIncompatibleMethodOverride]
        return Compare('!=', self, _coerce_compare_operand(other, like=self, op='!='))

    __hash__ = object.__hash__

    # ---- 大小比较(数值/str) ----

    def __lt__(self: 'Expr[_OrderedT]', other: 'Expr[_OrderedT] | _OrderedT') -> 'Expr[bool]':
        return _compare_ordered('<', self, other)

    def __le__(self: 'Expr[_OrderedT]', other: 'Expr[_OrderedT] | _OrderedT') -> 'Expr[bool]':
        return _compare_ordered('<=', self, other)

    def __gt__(self: 'Expr[_OrderedT]', other: 'Expr[_OrderedT] | _OrderedT') -> 'Expr[bool]':
        return _compare_ordered('>', self, other)

    def __ge__(self: 'Expr[_OrderedT]', other: 'Expr[_OrderedT] | _OrderedT') -> 'Expr[bool]':
        return _compare_ordered('>=', self, other)

    # ---- `+`(str 拼接 / 数值相加;JS 侧同一运算符) ----

    @overload
    def __add__(self: 'Expr[str]', other: 'Expr[str] | str') -> 'Expr[str]': ...
    @overload
    def __add__(self: 'Expr[int]', other: 'Expr[int] | int') -> 'Expr[int]': ...
    @overload
    def __add__(self: 'Expr[float]', other: 'Expr[float] | Expr[int] | float | int') -> 'Expr[float]': ...
    def __add__(self, other: object) -> 'Expr[Any]':
        return _concat(self, _coerce_add_operand(other))

    @overload
    def __radd__(self: 'Expr[str]', other: str) -> 'Expr[str]': ...
    @overload
    def __radd__(self: 'Expr[int]', other: int) -> 'Expr[int]': ...
    @overload
    def __radd__(self: 'Expr[float]', other: float | int) -> 'Expr[float]': ...
    def __radd__(self, other: object) -> 'Expr[Any]':
        return _concat(_coerce_add_operand(other), self)

    # ---- 防线:布尔上下文/容器协议全部抛错 ----

    def __bool__(self) -> NoReturn:
        raise TypeError(_BOOL_CONTEXT_HINT)

    def __len__(self) -> NoReturn:
        raise TypeError(
            f"Expr 不支持 len();长度判断请写成比较表达式(如 expr != '')或移到服务端 handler。{_BOOL_CONTEXT_HINT}"
        )  # noqa: E501

    def __iter__(self) -> NoReturn:
        raise TypeError("Expr 不可迭代;M1 表达式子集不含循环,列表渲染(Each 容器)见 M2 计划")

    def __contains__(self, item: object) -> NoReturn:
        raise TypeError(f"Expr 不支持 in 成员判断;请用 == / != 组合,或移到服务端 handler。{_BOOL_CONTEXT_HINT}")

    # ---- 双端求值与依赖收集 ----

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        """编译为 JS 表达式;scope 提供每个叶子(ClientVal/PropRef)对应的 JS 变量名。

        复合子表达式一律加括号,输出与 JS 运算符优先级解耦;叶子不加。
        """
        raise NotImplementedError

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> T:
        """Python 侧按 JS 同一语义求值;叶子取 snapshot 中的值,缺席回落到叶子初始值。"""
        raise NotImplementedError

    def refs(self) -> 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]':
        """依赖收集:返回树中全部叶子(按文档序去重),供编译期校验。"""
        out: list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]] = []
        self._collect_refs(out, set())
        return out

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        raise NotImplementedError


def _child_js(child: 'Expr[Any]', scope: 'Mapping[Expr[Any], str]') -> str:
    js = child.to_js(scope)
    if isinstance(child, (LiteralNode, ClientVal, PropRef, ItemRef)):
        return js
    return f'({js})'


def _scope_var(leaf: 'Expr[Any]', scope: 'Mapping[Expr[Any], str]') -> str:
    var = scope.get(leaf)
    if var is None:
        raise KeyError(f"{leaf!r} 不在 to_js scope 中;编译器为页面每个叶子提供变量名,测试请手工构造 scope 字典")
    return var


class LiteralNode(Expr[T]):
    """字面量叶子;运算中混入的普通 Python 值被包装为此节点。"""

    __slots__ = ('type', 'value')

    def __init__(self, value: T) -> None:
        self.type = _infer_type(value, owner='表达式字面量')
        self.value = value

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        return _js_literal(self.value)

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> T:
        return self.value

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        return

    def __repr__(self) -> str:
        return f'LiteralNode({self.value!r})'


class ClientVal(Expr[T]):
    """客户端状态叶子:声明为 Page 类字段,由受控组件绑定(checked=/value=)获得唯一写者。

    Python 侧无值语义(诚实泛型,不做 TYPE_CHECKING 值代理:值代理会把 `~thinking`
    推成 int,毁掉运算符 DX)。owner 由 Page.__init_subclass__ 刻写。
    """

    __slots__ = ('type', 'default', '_owner')

    def __init__(self, default: T) -> None:
        self.type = _infer_type(default, owner='ClientVal 默认值')
        self.default = default
        self._owner: str | None = None

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        return _scope_var(self, scope)

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> T:
        if snapshot is not None and self in snapshot:
            return cast('T', snapshot[self])
        return self.default

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        if id(self) not in seen:
            seen.add(id(self))
            out.append(self)

    def __repr__(self) -> str:
        return f'ClientVal({self.default!r}, owner={self._owner or "<未挂载>"})'


def read_owner(val: 'ClientVal[Any]') -> str | None:
    """框架内部:读取 ClientVal 的 owner(如 'SettingsPage.thinking')。"""
    return val._owner  # pyright: ignore[reportPrivateUsage]


def write_owner(val: 'ClientVal[Any]', owner: str) -> None:
    """框架内部:刻写 owner;仅 Page 收集流程调用。"""
    val._owner = owner  # pyright: ignore[reportPrivateUsage]


class PropRef(Expr[T]):
    """受控组件值叶子:由 value_of() 构造;anchor 编译期经 anchor_of 惰性解析
    (类体执行时组件尚未刻 anchor)。"""

    __slots__ = ('type', 'component', 'prop')

    def __init__(self, component: 'Component', prop: str, type_: ExprType) -> None:
        self.type = type_
        self.component = component
        self.prop = prop

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        return _scope_var(self, scope)

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> T:
        if snapshot is not None and self in snapshot:
            return cast('T', snapshot[self])
        current: object = getattr(self.component, self.prop)
        if isinstance(current, Expr):
            # 受控 prop 绑定了 ClientVal:初始值递归取绑定源
            return cast('T', cast('Expr[Any]', current).evaluate(snapshot))
        return cast('T', current)

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        if id(self) not in seen:
            seen.add(id(self))
            out.append(self)

    def __repr__(self) -> str:
        return f'PropRef({type(self.component).__name__}.{self.prop})'


class ItemRef(Expr[T]):
    """Each 模板的项字段叶子(M2 Phase 6):由 ItemProxy 属性访问构造并 memoize
    (scope/snapshot 按身份哈希,同字段必须复用同一叶子)。

    loop_token 标识归属的 Each 实例;编译期 checks 据此拒绝 ItemRef 逃逸出模板。
    field 为 '' 表示标量项(整个 item 即值)。evaluate 需要 item_snapshot() 构造的快照。
    """

    __slots__ = ('type', 'loop_token', 'field')

    def __init__(self, loop_token: object, field: str, type_: ExprType) -> None:
        self.type = type_
        self.loop_token = loop_token
        self.field = field

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        return _scope_var(self, scope)

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> T:
        if snapshot is not None and self in snapshot:
            return cast('T', snapshot[self])
        raise KeyError(f"{self!r} 没有值:ItemRef 求值需要 item_snapshot(each, item) 构造的快照")

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        if id(self) not in seen:
            seen.add(id(self))
            out.append(self)

    def __repr__(self) -> str:
        return f'ItemRef(.{self.field})' if self.field else 'ItemRef(<item>)'


class UnaryNot(Expr[bool]):
    """`~`:JS 侧 `!`。"""

    __slots__ = ('type', 'operand')

    def __init__(self, operand: 'Expr[bool]') -> None:
        self.type = ExprType.BOOL
        self.operand = operand

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        return f'!{_child_js(self.operand, scope)}'

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> bool:
        return not self.operand.evaluate(snapshot)

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        self.operand._collect_refs(out, seen)

    def __repr__(self) -> str:
        return f'~{self.operand!r}'


class BoolOp(Expr[bool]):
    """`&`/`|`:JS 侧 `&&`/`||`;操作数构造期强制 BOOL。"""

    __slots__ = ('type', 'op', 'left', 'right')

    def __init__(self, op: _BoolOpKind, left: 'Expr[bool]', right: 'Expr[bool]') -> None:
        self.type = ExprType.BOOL
        self.op: _BoolOpKind = op
        self.left = left
        self.right = right

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        return f'{_child_js(self.left, scope)} {_JS_BOOL_OP[self.op]} {_child_js(self.right, scope)}'

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> bool:
        if self.op == 'and':
            return bool(self.left.evaluate(snapshot) and self.right.evaluate(snapshot))
        return bool(self.left.evaluate(snapshot) or self.right.evaluate(snapshot))

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        self.left._collect_refs(out, seen)
        self.right._collect_refs(out, seen)

    def __repr__(self) -> str:
        return f'({self.left!r} {self.op} {self.right!r})'


class Compare(Expr[bool]):
    """比较:`==`/`!=` 映射 `===`/`!==`,大小比较原样。"""

    __slots__ = ('type', 'op', 'left', 'right')

    def __init__(self, op: _CompareOp, left: 'Expr[Any]', right: 'Expr[Any]') -> None:
        self.type = ExprType.BOOL
        self.op: _CompareOp = op
        self.left = left
        self.right = right

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        return f'{_child_js(self.left, scope)} {_JS_COMPARE[self.op]} {_child_js(self.right, scope)}'

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> bool:
        compare = _PY_COMPARE[self.op]
        return bool(compare(self.left.evaluate(snapshot), self.right.evaluate(snapshot)))

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        self.left._collect_refs(out, seen)
        self.right._collect_refs(out, seen)

    def __repr__(self) -> str:
        return f'({self.left!r} {self.op} {self.right!r})'


class Concat(Expr[T]):
    """`+`:STR 拼接或数值相加(构造期已保证两侧同类别)。"""

    __slots__ = ('type', 'left', 'right')

    def __init__(self, type_: ExprType, left: 'Expr[Any]', right: 'Expr[Any]') -> None:
        self.type = type_
        self.left = left
        self.right = right

    def to_js(self, scope: 'Mapping[Expr[Any], str]') -> str:
        return f'{_child_js(self.left, scope)} + {_child_js(self.right, scope)}'

    def evaluate(self, snapshot: 'Mapping[Expr[Any], object] | None' = None) -> T:
        left: Any = self.left.evaluate(snapshot)
        right: Any = self.right.evaluate(snapshot)
        return cast('T', left + right)

    def _collect_refs(self, out: 'list[ClientVal[Any] | PropRef[Any] | ItemRef[Any]]', seen: set[int]) -> None:
        self.left._collect_refs(out, seen)
        self.right._collect_refs(out, seen)

    def __repr__(self) -> str:
        return f'({self.left!r} + {self.right!r})'


# ---- 构造期类型检查与包装 ----


def _require_bool(expr: 'Expr[Any]', op: str) -> 'Expr[bool]':
    if expr.type is not ExprType.BOOL:
        raise TypeError(
            f"'{op}' 的操作数必须是 bool 表达式(收到 {expr.type.value});"
            f"Python 中 {op} 优先级高于比较运算,比较请加括号:(a == b) {op} (c == d)"
        )
    return cast('Expr[bool]', expr)


def _coerce_bool_operand(other: object, op: str) -> 'Expr[bool]':
    if isinstance(other, Expr):
        return _require_bool(cast('Expr[Any]', other), op)
    if isinstance(other, bool):
        return LiteralNode(other)
    raise TypeError(f"'{op}' 的操作数必须是 bool 表达式或 bool 字面量,收到 {type(other).__name__}")


def _same_category(a: ExprType, b: ExprType) -> bool:
    return a is b or (a in _NUMERIC and b in _NUMERIC)


def _coerce_compare_operand(other: object, *, like: 'Expr[Any]', op: str) -> 'Expr[Any]':
    other_expr: Expr[Any] = cast('Expr[Any]', other) if isinstance(other, Expr) else LiteralNode(other)
    if not _same_category(like.type, other_expr.type):
        raise TypeError(f"'{op}' 两侧类型不一致:{like.type.value} vs {other_expr.type.value};表达式不做隐式类型转换")
    return other_expr


def _compare_ordered(op: _CompareOp, left: 'Expr[Any]', right: object) -> 'Expr[bool]':
    if left.type is ExprType.BOOL:
        raise TypeError(f"bool 表达式不支持 '{op}' 大小比较;逻辑组合请用 & | ~")
    right_expr = _coerce_compare_operand(right, like=left, op=op)
    return Compare(op, left, right_expr)


def _coerce_add_operand(other: object) -> 'Expr[Any]':
    if isinstance(other, Expr):
        return cast('Expr[Any]', other)
    return LiteralNode(other)


def _concat(left: 'Expr[Any]', right: 'Expr[Any]') -> 'Expr[Any]':
    lt, rt = left.type, right.type
    if lt is ExprType.STR and rt is ExprType.STR:
        return Concat(ExprType.STR, left, right)
    if lt in _NUMERIC and rt in _NUMERIC:
        result = ExprType.FLOAT if ExprType.FLOAT in (lt, rt) else ExprType.INT
        return Concat(result, left, right)
    raise TypeError(f"'+' 需要两侧同为 str 或同为数值:{lt.value} + {rt.value}")


# ---- 公开工厂 ----


def cond(value: 'Expr[bool] | bool') -> 'Expr[bool]':
    """类型收窄逃生舱:字面量在左(`True == expr`)时 pyright 会把结果推成 bool,
    运行期实际是 Expr;cond() 把静态类型收回 Expr[bool],运行时校验其确为 bool 表达式。"""
    if isinstance(value, Expr):
        return _require_bool(cast('Expr[Any]', value), 'cond()')
    return LiteralNode(value)


def value_of(component: 'ControlledMixin[T]') -> 'Expr[T]':
    """受控组件当前值作为表达式源(design.md §3.4)。

    仅接受混入 ControlledMixin 的组件;PasswordInput 等敏感组件在类型层
    (不混入)与运行时(此处)双层拒绝(design.md §3.8)。
    """
    from pyshade.components.base import Component, ControlledMixin, controlled_prop_of, is_sensitive

    if isinstance(component, Component) and is_sensitive(component):
        raise TypeError(
            f"{type(component).__name__} 是敏感输入:值只随 submit=True 的事件跨界,不能作为表达式源(design.md §3.8)"
        )
    # 静态层由参数注解保证;运行时兜底无类型调用
    if not isinstance(component, ControlledMixin) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        component, Component
    ):
        raise TypeError(f"value_of() 需要受控组件(ControlledMixin),收到 {type(component).__name__}")
    prop = controlled_prop_of(component)
    current: object = getattr(component, prop)
    if isinstance(current, Expr):
        expr_type = cast('Expr[Any]', current).type
    else:
        expr_type = _infer_type(current, owner=f'{type(component).__name__}.{prop}')
    return PropRef(component, prop, expr_type)
