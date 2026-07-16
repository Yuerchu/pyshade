"""客户端 action 基类(M4,design.md §3.11 route 先例的推广)。

事件 prop 除 handler 外还可赋"零 IPC 客户端 action"标记:navigate(Page) 切页、
set_color_scheme() 切配色。共性收拢在 ClientAction:
- 不是 handler,不可调用、不可作条件判断(误用即抛);
- 不进 EventRegistry(无 handlerId),编译为对应的 rt.* 调用;
- pydantic 按 is_instance 校验(事件 prop 注解 `Handler | ClientAction | None`)。

本模块运行时是叶子(零框架依赖),nav/scheme/components 可安全依赖。
"""

from typing import NoReturn

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema


class ClientAction:
    """零 IPC 客户端 action 标记的基类(不是 handler)。"""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        # 事件 prop 注解 `Handler | ClientAction | None` 时按 isinstance 校验
        return core_schema.is_instance_schema(cls)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        # is-instance 无法 JSON 化;宽松占位让用户侧 model_json_schema() 可用(M4,同 Expr)
        return {'title': 'ClientAction', 'description': 'Zero-IPC client action (navigate / set_color_scheme).'}

    def __bool__(self) -> NoReturn:
        raise TypeError(f"{type(self).__name__} 不能用于条件判断;它只能赋给事件 prop(如 on_click=)")

    def __call__(self, *args: object, **kwargs: object) -> NoReturn:
        raise TypeError(f"{type(self).__name__} 不是 handler,不能被调用;它只能赋给事件 prop(如 on_click=)")
