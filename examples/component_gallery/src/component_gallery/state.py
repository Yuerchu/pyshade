"""ServerState:进度演示与 Each 列表数据。"""

from pydantic import BaseModel

from pyshade.state import ServerState


class ChangelogEntry(BaseModel):
    version: str
    note: str


class GalleryDemoState(ServerState):
    upload_pct: int = 40
    changelog: list[ChangelogEntry] = [
        ChangelogEntry(version='0.1.0', note='首个端到端原型'),
        ChangelogEntry(version='0.2.0', note='表达式系统与推送'),
        ChangelogEntry(version='0.3.0', note='组件铺量与零 Node 打包'),
    ]


gallery_state = GalleryDemoState()
