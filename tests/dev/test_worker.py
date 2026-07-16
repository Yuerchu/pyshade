"""dev worker:uvicorn 优雅关闭超时锚定(SSE 常驻连接下默认 None 会无限等,
POSIX 热重载每次固定 +10s;spy 断言参数,不起真 server)。"""

from pathlib import Path
from typing import Any

import pytest

import pyshade.bundler as bundler_mod
import pyshade.cli as cli_mod
from pyshade.app import ShadeApp
from pyshade.bundler import BundleResult
from pyshade.components import Text
from pyshade.dev._worker import worker_main
from pyshade.page import Page


class WorkerProbePage(Page):
    hello = Text('worker')


def test_worker_sets_graceful_shutdown_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    captured: dict[str, Any] = {}

    def fake_run(app: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    def fake_bundle(app: Any, out_dir: Any, **kwargs: Any) -> BundleResult:
        dist = Path(out_dir)
        dist.mkdir(parents=True, exist_ok=True)
        (dist / 'index.html').write_text('<head></head>', encoding='utf-8')
        return BundleResult(out_dir=dist, app_js_bytes=0, duration_ms=0)

    def fake_load(spec: str) -> ShadeApp:
        return ShadeApp(pages=[WorkerProbePage])

    monkeypatch.setattr(uvicorn, 'run', fake_run)
    monkeypatch.setattr(bundler_mod, 'bundle_app', fake_bundle)
    monkeypatch.setattr(cli_mod, 'load_app', fake_load)

    assert worker_main(['probe:app', '--port', '8765', '--workdir', str(tmp_path)]) == 0
    assert captured['timeout_graceful_shutdown'] == 1
    assert captured['lifespan'] == 'on'
