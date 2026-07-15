"""零依赖模板渲染:`{{key}}` 逐一替换 + 残留检测(不引模板引擎)。"""


class RenderError(ValueError):
    """模板渲染失败:占位符残留或值非法。"""


def render(template: str, params: dict[str, str]) -> str:
    """渲染模板;完成后断言无 `{{` 残留(防漏参/拼写错)。"""
    out = template
    for key, value in params.items():
        out = out.replace('{{' + key + '}}', value)
    if '{{' in out:
        start = out.index('{{')
        fragment = out[start : start + 60].splitlines()[0]
        raise RenderError(f"模板渲染后仍有未替换占位符: {fragment!r};已提供参数 {sorted(params)}")
    return out
