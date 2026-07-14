"""组件 DTO 基类与事件标记(design.md §3.5)。

本包保持纯 DTO:不 import 编译器/页面/事件注册表,可独立使用。
"""

from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, PrivateAttr

Handler = Callable[..., Any]
"""事件处理器引用;运行期只存引用,签名由编译器校验(pyshade.events)。"""


class EventSpec:
    """Annotated 元数据:标记事件字段。

    kind 描述前端事件语义('click' / 'change');submit 语义由组件 props 表达。
    """

    __slots__ = ('kind',)

    def __init__(self, kind: str) -> None:
        self.kind = kind


class Component(BaseModel):
    """所有 UI 组件 DTO 的基类。

    - `extra='forbid'`:未知 prop 在用户模块 import 时即 ValidationError。
    - `revalidate_instances` 必须保持 Pydantic 默认 'never':布局的单父检测与
      anchor 刻写依赖实例同一性(children 不深拷贝),L0 测试固化此前提。
    """

    model_config = ConfigDict(extra='forbid')

    visible: bool = True
    """M0:服务端 Update 驱动显隐;M1 同一 prop 升级接受 ClientVal[bool] 表达式。"""

    _anchor: str | None = PrivateAttr(default=None)
    """Page 收集时刻写,如 'LoginPage.username';匿名后代为路径形式 'LoginPage.card[0]'。"""

    _shade_tag: ClassVar[str] = ''
    """生成代码中的组件名;emitter 注册表的分发键。"""

    _sensitive: ClassVar[bool] = False
    """design.md §3.8:True → 值仅随 submit 事件跨界,组件不得声明事件字段。"""


def read_anchor(component: Component) -> str | None:
    """框架内部:读取组件 anchor(同模块访问私有属性的受控出口)。"""
    return component._anchor  # pyright: ignore[reportPrivateUsage]


def write_anchor(component: Component, anchor: str) -> None:
    """框架内部:刻写组件 anchor;仅 Page 收集流程调用。"""
    component._anchor = anchor  # pyright: ignore[reportPrivateUsage]


def component_tag(component: Component) -> str:
    """框架内部:读取组件的 emitter 分发键。"""
    return type(component)._shade_tag  # pyright: ignore[reportPrivateUsage]


def is_sensitive(component: Component) -> bool:
    """框架内部:组件是否为敏感输入(design.md §3.8)。"""
    return type(component)._sensitive  # pyright: ignore[reportPrivateUsage]
