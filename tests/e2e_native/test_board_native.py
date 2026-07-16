"""task_board 编译产物的真机验证:Each 第 N 项点击、双向导航、服务端 Navigate。

dist 经 PYSHADE_E2E_BOARD_DIST 指定(CI 用 `pyshade bundle` 的零 Node 产物),缺席即 skip。
harness 每进程只能 run 一次(tao EventLoop 限制),login_form 已占用本进程,
故以子进程运行 `python -m pyshade.testing --suites spa.*`,读回 report.json 断言。
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.e2e_native

REPO = Path(__file__).parent.parent.parent


@pytest.fixture(scope='module')
def board_report() -> dict[str, Any]:
    dist_env = os.environ.get('PYSHADE_E2E_BOARD_DIST')
    if not dist_env:
        pytest.skip("未设置 PYSHADE_E2E_BOARD_DIST(先 pyshade bundle task_board.app:app)")
    dist = Path(dist_env)
    if not (dist / 'index.html').exists():
        pytest.skip(f"board dist 不存在:{dist}")
    testkit = Path(os.environ.get('PYSHADE_E2E_TESTKIT', REPO / 'frontend' / 'dist-testkit' / 'testkit.js'))
    if not testkit.exists():
        pytest.skip("缺 testkit:先 pnpm -C frontend build:testkit")
    try:
        import pytauri_wheel.lib  # noqa: F401  # pyright: ignore[reportUnusedImport]
    except Exception:
        pytest.skip("pytauri-wheel 不可用:uv sync --extra native")

    report_dir = REPO / 'reports' / 'native-board'
    board_src = REPO / 'examples' / 'task_board' / 'src'
    env = {**os.environ, 'PYTHONPATH': f'{board_src}{os.pathsep}{os.environ.get("PYTHONPATH", "")}'}
    proc = subprocess.run(
        [
            sys.executable,
            '-m',
            'pyshade.testing',
            '--runtime',
            'task_board.runtime:build_runtime',
            '--src-tauri-dir',
            str(board_src / 'task_board'),
            '--dist',
            str(dist),
            '--testkit',
            str(testkit),
            '--suites',
            'spa.each_click,spa.navigate',
            '--report-dir',
            str(report_dir),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=180,
        check=False,
    )
    report_file = report_dir / 'report.json'
    assert report_file.exists(), (
        f"harness 未产出报告(exit={proc.returncode})\nstdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}"
    )
    return json.loads(report_file.read_text(encoding='utf-8'))


def _case(report: dict[str, Any], case_id: str) -> dict[str, Any]:
    case = next((c for c in report['cases'] if c['id'] == case_id), None)
    assert case is not None, f"用例 {case_id} 不在报告中;cases={[c['id'] for c in report['cases']]}"
    return case


def test_each_click_nth_item(board_report: dict[str, Any]) -> None:
    case = _case(board_report, 'spa.each_click')
    assert case['status'] == 'pass', case


def test_navigate_round_trip(board_report: dict[str, Any]) -> None:
    case = _case(board_report, 'spa.navigate')
    assert case['status'] == 'pass', case
