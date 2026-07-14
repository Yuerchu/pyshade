from typing import Any

from pyshade.components.base import Component


class Text(Component):
    """纯文本显示;Python 回传更新 UI 的显示锚点。"""

    _shade_tag = 'Text'

    text: str = ''
    muted: bool = False

    def __init__(self, text: str = '', *, muted: bool = False, visible: bool = True) -> None:
        data: dict[str, Any] = {'text': text, 'muted': muted, 'visible': visible}
        super().__init__(**data)
