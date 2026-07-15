"""事件 handler:画廊只做最小回传演示。"""

from component_gallery.state import gallery_state
from pyshade.events import EventContext


def on_submit(ctx: EventContext) -> None: ...


def on_confirm_reset(ctx: EventContext) -> None:
    gallery_state.upload_pct = 0


def on_cancel_reset(ctx: EventContext) -> None: ...
