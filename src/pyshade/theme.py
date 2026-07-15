"""主题口子(M3,design.md §3.5/§6):只暴露 CSS 变量层(shadcn token),不碰 Tailwind class。

字段全量镜像 frontend/src/index.css 的 :root token(snake_case ↔ --kebab-case),
对账测试锚定两边不漂移。值原样透传(oklch()/hex/关键字/var() 都是合法 CSS,不做解析白名单),
只设注入护栏(禁 `;{}` 与换行)。dark mode 留 M4:theme.css 把亮色包在 :root{} 里,
将来追加 .dark{} 块不破本接口。
"""

from pydantic import BaseModel, ConfigDict, field_validator

_FORBIDDEN_CHARS = frozenset(';{}\n\r')


class Theme(BaseModel):
    """`ShadeApp(theme=Theme(primary='oklch(0.55 0.2 260)', radius='0.75rem'))`。

    全部字段可选;只有设置的 token 会进 theme.gen.css 覆盖 :root 默认值。
    未知 token 由 extra='forbid' 在构造期报错。
    """

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
    def _css_value_guard(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("token 值不能为空串")
        if any(char in _FORBIDDEN_CHARS for char in stripped):
            raise ValueError("token 值含非法字符(; { } 或换行)——CSS 注入护栏")
        return stripped


def theme_tokens(theme: Theme) -> dict[str, str]:
    """已设置的 token(kebab-case → 值),声明序。"""
    return {name.replace('_', '-'): value for name, value in theme.model_dump().items() if value is not None}
