"""settings_panel 示例的自动化验证:编译产物形态 + 事件链路(不起 WebView)。"""

from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport
from settings_panel.app import app
from settings_panel.runtime import build_runtime
from settings_panel.state import panel

from pyshade.compiler import compile_app

pytestmark = pytest.mark.anyio


def test_compiles_with_all_binding_forms(tmp_path: Path) -> None:
    compile_app(app, tmp_path)
    tsx = (tmp_path / 'pages' / 'SettingsPanelPage.gen.tsx').read_text(encoding='utf-8')
    # 表达式内联(客户端所有)
    assert 'disabled={!thinkingValue}' in tsx
    assert '{(thinkingValue && darkValue) && (' in tsx
    # ClientVal 共用 useState(client_bind)
    assert 'const [nickValue, setNickValue] = useState<string>("");' in tsx
    # ServerRef → $s: 命名空间 + push 订阅
    assert 'rt.ov("$s:PanelState", "status", "就绪")' in tsx
    assert 'push: true' in tsx
    assert 'boundProps: [' in tsx


async def test_save_event_auto_diff() -> None:
    _registry, fastapi_app = build_runtime()
    panel.status = '就绪'
    panel.save_count = 0

    transport = ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url='http://t') as client:
        response = await client.post(
            '/_shade/event/SettingsPanelPage.save.on_click',
            json={'values': {'nick': '于小丘', 'thinking': True}},
        )
    assert response.status_code == 200
    patches = response.json()['patches']
    assert patches == [{'target': '$s:PanelState', 'props': {'save_count': 1, 'status': '已保存(第 1 次),欢迎 于小丘'}}]
    panel.status = '就绪'
    panel.save_count = 0
