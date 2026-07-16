"""主题口子(M3 亮色 / M4 暗色,design.md §3.6):只暴露 CSS 变量层(shadcn token)。

字段全量镜像 frontend/src/index.css 的 :root 与 .dark token(snake_case ↔ --kebab-case),
对账测试锚定两边不漂移。值原样透传(oklch()/hex/关键字/var() 都是合法 CSS,不做解析白名单),
只设注入护栏(禁 `;{}` 与换行)。

暗色语义:`Theme` 顶层字段 = 亮色 token;`dark=ThemeTokens(...)` = 暗色 token,未设的
暗色 token 用预编译 style.css 内置的 shadcn 暗色默认值——与直接编辑 index.css 的
:root/.dark 心智一致。radius 是模式无关 token(.dark 不重定义)。
"""

from pydantic import BaseModel, ConfigDict, field_validator

_FORBIDDEN_CHARS = frozenset(';{}\n\r')

MODE_INDEPENDENT_TOKENS = frozenset({'radius'})
"""模式无关 token:emit 时进裸 :root 段,暗色块不重定义(对账测试同源消费)。"""


class ThemeTokens(BaseModel):
    """一套配色的 token 集(亮色或暗色);全部字段可选,只有设置的才发射。"""

    model_config = ConfigDict(frozen=True, extra='forbid')

    background: str | None = None
    foreground: str | None = None
    card: str | None = None
    card_foreground: str | None = None
    popover: str | None = None
    popover_foreground: str | None = None
    primary: str | None = None
    primary_foreground: str | None = None
    secondary: str | None = None
    secondary_foreground: str | None = None
    muted: str | None = None
    muted_foreground: str | None = None
    accent: str | None = None
    accent_foreground: str | None = None
    destructive: str | None = None
    destructive_foreground: str | None = None
    border: str | None = None
    input: str | None = None
    ring: str | None = None
    radius: str | None = None
    sidebar: str | None = None
    sidebar_foreground: str | None = None
    sidebar_primary: str | None = None
    sidebar_primary_foreground: str | None = None
    sidebar_accent: str | None = None
    sidebar_accent_foreground: str | None = None
    sidebar_border: str | None = None
    sidebar_ring: str | None = None

    @field_validator('*')
    @classmethod
    def _css_value_guard(cls, value: object) -> object:
        # '*' 也会命中子类新增的非 str 字段(如 Theme.dark),只守护 token 值
        if value is None or not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("token 值不能为空串")
        if any(char in _FORBIDDEN_CHARS for char in stripped):
            raise ValueError("token 值含非法字符(; { } 或换行)——CSS 注入护栏")
        return stripped


class Theme(ThemeTokens):
    """`ShadeApp(theme=Theme(primary='...', dark=ThemeTokens(primary='...')))`。

    顶层字段覆盖亮色 :root 默认值;dark 覆盖暗色 .dark 默认值。
    未知 token 由 extra='forbid' 在构造期报错。
    """

    dark: 'ThemeTokens | None' = None


def theme_tokens(tokens: ThemeTokens) -> dict[str, str]:
    """已设置的 token(kebab-case → 值),声明序;非 str 字段(Theme.dark)天然排除。"""
    return {name.replace('_', '-'): value for name, value in tokens.model_dump().items() if isinstance(value, str)}
