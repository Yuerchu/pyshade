"""选项数据模型(Select/RadioGroup):选项是数据 prop,不是子组件。

服务端可 `Update(select, options=[...])` 整表替换;动态选项(Expr/ServerRef)与
Each 同批 M3。str 简写归一化为 value=label 的 Option。
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class Option(BaseModel):
    """一个选项:value 是回传值,label 是展示文本。"""

    model_config = ConfigDict(extra='forbid', frozen=True)

    value: str = Field(description="Value sent back to the server when the option is selected.")
    label: str = Field(description="Human-readable text displayed for the option.")


def normalize_options(options: Sequence[str | Option]) -> list[Option]:
    """str 简写 → Option(value=s, label=s);Option 原样保留。"""
    out: list[Option] = []
    for item in options:
        if isinstance(item, str):
            out.append(Option(value=item, label=item))
        else:
            out.append(item)
    return out
