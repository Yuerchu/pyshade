"""真机 E2E:session fixture 跑一次 harness,7 个用例各断言各的。

前置产物:pnpm -C frontend build && pnpm -C frontend build:testkit
依赖:uv sync --group native
"""

import os
from pathlib import Path

import pytest

from pyshade.testing import TestReport

REPO = Path(__file__).parent.parent.parent


@pytest.fixture(scope='session')
def native_report() -> TestReport:
    # bundle-zero-node job 经 env 把真机 E2E 指向 esbuild 产物(与 vite 产物 job 互为对照)
    dist = Path(os.environ.get('PYSHADE_E2E_DIST', REPO / 'frontend' / 'dist'))
    testkit = Path(os.environ.get('PYSHADE_E2E_TESTKIT', REPO / 'frontend' / 'dist-testkit' / 'testkit.js'))
    if not (dist / 'index.html').exists():
        pytest.skip("缺前端产物:先 pnpm -C frontend build")
    if not testkit.exists():
        pytest.skip("缺 testkit:先 pnpm -C frontend build:testkit")
    try:
        import pytauri_wheel.lib  # noqa: F401  # pyright: ignore[reportUnusedImport]
    except Exception:
        pytest.skip("pytauri-wheel 不可用:uv sync --group native")

    from login_form.runtime import build_runtime

    from pyshade.testing import HarnessConfig
    from pyshade.testing._harness import NativeHarness

    _registry, fastapi_app = build_runtime()
    config = HarnessConfig(
        src_tauri_dir=REPO / 'examples' / 'login_form' / 'src' / 'login_form',
        frontend_dist=dist,
        testkit_bundle=testkit,
        report_dir=REPO / 'reports' / 'native',
    )
    return NativeHarness(fastapi_app, config).run()
